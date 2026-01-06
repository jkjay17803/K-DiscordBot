# role_manager.py - 티어 역할 관리

import asyncio
import discord
from config import TIER_ROLES
from database import get_all_users_for_nickname_refresh


def get_tier_for_level(level: int) -> tuple[str, str] | None:
    """
    레벨에 해당하는 티어 정보 반환
    Returns: (티어_이름, 역할_이름) 또는 None
    """
    # 레벨이 높은 순서대로 정렬 (가장 높은 티어부터 확인)
    sorted_tiers = sorted(TIER_ROLES.items(), key=lambda x: x[1][0], reverse=True)
    
    for tier_name, (required_level, role_name) in sorted_tiers:
        if level >= required_level:
            return (tier_name, role_name)
    
    return None


async def update_tier_role(member: discord.Member, level: int) -> tuple[bool, str | None, str | None]:
    """
    사용자의 티어 역할 업데이트
    레벨에 맞는 티어 역할을 지급하고 이전 티어 역할을 제거합니다.
    Returns: (성공 여부, 이전 티어 이름, 새 티어 이름)
    티어가 변경되지 않았으면 이전 티어와 새 티어가 같거나 None입니다.
    """
    try:
        # 봇이 역할을 관리할 수 있는 권한이 있는지 확인
        if not member.guild.me.guild_permissions.manage_roles:
            print(f"[RoleManager] No permission to manage roles for {member.name}")
            return (False, None, None)
        
        # 현재 레벨에 해당하는 티어 확인
        tier_info = get_tier_for_level(level)
        if tier_info is None:
            # 티어가 없으면 모든 티어 역할 제거
            await remove_all_tier_roles(member)
            return (True, None, None)
        
        tier_name, target_role_name = tier_info
        
        # 서버에서 역할 찾기
        target_role = discord.utils.get(member.guild.roles, name=target_role_name)
        if target_role is None:
            print(f"[RoleManager] Role '{target_role_name}' not found in guild")
            return (False, None, None)
        
        # 사용자가 이미 해당 역할을 가지고 있는지 확인
        has_target_role = target_role in member.roles
        
        # 모든 티어 역할 목록 가져오기
        all_tier_role_names = [role_name for _, (_, role_name) in TIER_ROLES.items()]
        all_tier_roles = [discord.utils.get(member.guild.roles, name=role_name) 
                         for role_name in all_tier_role_names]
        all_tier_roles = [role for role in all_tier_roles if role is not None]
        
        # 사용자가 가지고 있는 티어 역할 찾기
        user_tier_roles = [role for role in all_tier_roles if role in member.roles]
        
        # 이전 티어 이름 찾기
        old_tier_name = None
        if user_tier_roles:
            # 사용자가 가지고 있는 티어 역할의 이름으로 이전 티어 찾기
            old_role_name = user_tier_roles[0].name
            for tier_key, (_, role_name) in TIER_ROLES.items():
                if role_name == old_role_name:
                    old_tier_name = tier_key
                    break
        
        # 이미 올바른 역할만 가지고 있으면 스킵 (티어 변경 없음)
        if has_target_role and len(user_tier_roles) == 1 and user_tier_roles[0] == target_role:
            return (True, tier_name, tier_name)  # 티어 변경 없음
        
        # 티어가 변경되었는지 확인
        tier_changed = old_tier_name != tier_name
        
        # 이전 티어 역할 제거
        roles_to_remove = [role for role in user_tier_roles if role != target_role]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=f"티어 변경: 레벨 {level} → {tier_name}")
                print(f"[RoleManager] Removed tier roles from {member.name}: {[r.name for r in roles_to_remove]}")
            except discord.Forbidden:
                print(f"[RoleManager] No permission to remove roles from {member.name}")
                return (False, old_tier_name, tier_name)
            except discord.HTTPException as e:
                print(f"[RoleManager] Failed to remove roles from {member.name}: {e}")
                return (False, old_tier_name, tier_name)
        
        # 새로운 티어 역할 추가 (아직 없는 경우)
        if not has_target_role:
            try:
                await member.add_roles(target_role, reason=f"티어 달성: 레벨 {level} → {tier_name}")
                print(f"[RoleManager] Added tier role to {member.name}: {target_role_name} (Level {level})")
            except discord.Forbidden:
                print(f"[RoleManager] No permission to add role to {member.name}")
                return (False, old_tier_name, tier_name)
            except discord.HTTPException as e:
                print(f"[RoleManager] Failed to add role to {member.name}: {e}")
                return (False, old_tier_name, tier_name)
        
        return (True, old_tier_name, tier_name)
        
    except Exception as e:
        print(f"[RoleManager] Error updating tier role for {member.name}: {e}")
        return (False, None, None)


async def remove_all_tier_roles(member: discord.Member) -> bool:
    """
    사용자에게서 모든 티어 역할 제거
    """
    try:
        # 모든 티어 역할 목록 가져오기
        all_tier_role_names = [role_name for _, (_, role_name) in TIER_ROLES.items()]
        all_tier_roles = [discord.utils.get(member.guild.roles, name=role_name) 
                         for role_name in all_tier_role_names]
        all_tier_roles = [role for role in all_tier_roles if role is not None]
        
        # 사용자가 가지고 있는 티어 역할 찾기
        user_tier_roles = [role for role in all_tier_roles if role in member.roles]
        
        if not user_tier_roles:
            return True
        
        # 모든 티어 역할 제거
        try:
            await member.remove_roles(*user_tier_roles, reason="티어 역할 제거")
            print(f"[RoleManager] Removed all tier roles from {member.name}: {[r.name for r in user_tier_roles]}")
            return True
        except discord.Forbidden:
            print(f"[RoleManager] No permission to remove roles from {member.name}")
            return False
        except discord.HTTPException as e:
            print(f"[RoleManager] Failed to remove roles from {member.name}: {e}")
            return False
        
    except Exception as e:
        print(f"[RoleManager] Error removing tier roles from {member.name}: {e}")
        return False


async def initial_tier_role_update(bot):
    """봇 시작 시 모든 사용자의 티어 역할을 즉시 업데이트"""
    print("[RoleManager] Starting initial tier role update...")
    
    # 모든 사용자 조회
    users = await get_all_users_for_nickname_refresh()
    
    updated_count = 0
    failed_count = 0
    
    for user_data in users:
        user_id = user_data['user_id']
        guild_id = user_data['guild_id']
        level = user_data['level']
        
        # 서버 조회
        guild = bot.get_guild(guild_id)
        if guild is None:
            continue
        
        # 멤버 조회
        member = guild.get_member(user_id)
        if member is None:
            continue
        
        # 티어 역할 업데이트 (축하 메시지는 보내지 않음 - 초기화이므로)
        success, old_tier, new_tier = await update_tier_role(member, level)
        if success:
            updated_count += 1
        else:
            failed_count += 1
        
        # API 레이트 리밋 방지를 위해 약간의 딜레이
        await asyncio.sleep(0.1)
    
    print(f"[RoleManager] Initial tier role update completed: {updated_count} updated, {failed_count} failed")

