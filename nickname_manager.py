# nickname_manager.py - 닉네임 레벨 표시 관리

import asyncio
import re
import discord
from config import NICKNAME_FORMAT, NICKNAME_REFRESH_INTERVAL
from database import get_all_users_for_nickname_refresh, update_last_nickname_update, get_user
from role_manager import update_tier_role
from utils import has_jk_role


def extract_level_from_nickname(nickname: str) -> int:
    """닉네임에서 레벨 추출"""
    if nickname is None:
        return None
    
    # [Lv.123] 형식에서 레벨 추출
    match = re.search(r'\[Lv\.(\d+)\]', nickname)
    if match:
        return int(match.group(1))
    return None


def get_original_nickname(nickname: str) -> str:
    """닉네임에서 레벨 표시와 JK 아이콘을 제거한 원래 닉네임 추출"""
    if nickname is None:
        return ""
    # 레벨 표시 제거
    original = re.sub(r'\[Lv\.\d+\]\s*', '', nickname).strip()
    # JK 아이콘 제거
    original = re.sub(r'\[\s*✬\s*\]\s*', '', original).strip()
    return original if original else nickname


def format_nickname_with_jk(original_nickname: str) -> str:
    """JK 역할 사용자의 닉네임 형식화 (운영자 아이콘 추가)"""
    # 이미 JK 아이콘이 포함되어 있는지 확인
    if '[ ✬ ]' in original_nickname or '[✬]' in original_nickname:
        # 이미 올바른 형식이면 그대로 반환
        return original_nickname
    
    # 기존 JK 아이콘 제거 (다양한 형식 대응)
    clean_nickname = re.sub(r'\[\s*✬\s*\]\s*', '', original_nickname).strip()
    
    # JK 아이콘 추가
    formatted = f"[ ✬ ] {clean_nickname}"
    
    # Discord 닉네임 길이 제한 (32자)
    if len(formatted) > 32:
        # 아이콘을 유지하면서 원래 닉네임을 자름
        icon_part = "[ ✬ ] "
        max_original_length = 32 - len(icon_part)
        if max_original_length > 0:
            clean_nickname = clean_nickname[:max_original_length]
            formatted = icon_part + clean_nickname
        else:
            # 아이콘만으로도 32자를 넘으면 아이콘만 표시
            formatted = "[ ✬ ]"
    
    return formatted


def format_nickname_with_level(original_nickname: str, level: int) -> str:
    """레벨을 포함한 닉네임 형식화"""
    # 이미 레벨이 포함되어 있는지 확인
    current_level = extract_level_from_nickname(original_nickname)
    
    if current_level == level:
        # 이미 올바른 레벨이 표시되어 있으면 그대로 반환
        return original_nickname
    
    # 기존 레벨 표시 제거
    if current_level is not None:
        original_nickname = re.sub(r'\[Lv\.\d+\]\s*', '', original_nickname).strip()
    
    # 새 레벨 표시 추가
    formatted = NICKNAME_FORMAT.format(level=level, original_nickname=original_nickname)
    
    # Discord 닉네임 길이 제한 (32자)
    if len(formatted) > 32:
        # 레벨 표시를 유지하면서 원래 닉네임을 자름
        level_part = f"[Lv.{level}] "
        max_original_length = 32 - len(level_part)
        if max_original_length > 0:
            original_nickname = original_nickname[:max_original_length]
            formatted = level_part + original_nickname
        else:
            # 레벨 표시만으로도 32자를 넘으면 레벨만 표시
            formatted = f"[Lv.{level}]"
    
    return formatted


async def update_user_nickname(member, level: int):
    """사용자 닉네임에 레벨 표시 업데이트"""
    # 봇이 변경 중임을 표시 (무한 루프 방지)
    if hasattr(member.guild.me, '_nickname_update_in_progress'):
        member.guild.me._nickname_update_in_progress.add(member.id)
    
    try:
        # JK 역할을 가진 사용자는 운영자 아이콘 표시
        if has_jk_role(member):
            # 봇이 닉네임을 변경할 수 있는 권한이 있는지 확인
            if not member.guild.me.guild_permissions.manage_nicknames:
                return False
            
            # 사용자가 봇보다 높은 권한을 가지고 있으면 변경 불가
            if member.top_role >= member.guild.me.top_role and member != member.guild.owner:
                return False
            
            # 현재 닉네임 가져오기
            current_nickname = member.display_name or member.name
            original_nickname = get_original_nickname(current_nickname)
            new_nickname = format_nickname_with_jk(original_nickname)
            
            # 닉네임이 변경되지 않았으면 스킵
            if new_nickname == current_nickname:
                return True
            
            await member.edit(nick=new_nickname)
            await update_last_nickname_update(member.id, member.guild.id)
            print(f"[NicknameManager] Updated nickname for {member.name} to {new_nickname} (JK role)")
            return True
        
        # 봇이 닉네임을 변경할 수 있는 권한이 있는지 확인
        if not member.guild.me.guild_permissions.manage_nicknames:
            return False
        
        # 사용자가 봇보다 높은 권한을 가지고 있으면 변경 불가
        if member.top_role >= member.guild.me.top_role and member != member.guild.owner:
            return False
        
        # 현재 닉네임 가져오기 (display_name은 서버별 닉네임, 없으면 전역 닉네임)
        current_nickname = member.display_name or member.name
        new_nickname = format_nickname_with_level(current_nickname, level)
        
        # 닉네임이 변경되지 않았으면 스킵
        if new_nickname == current_nickname:
            return True
        
        await member.edit(nick=new_nickname)
        await update_last_nickname_update(member.id, member.guild.id)
        
        print(f"[NicknameManager] Updated nickname for {member.name} to {new_nickname}")
        return True
        
    except discord.Forbidden:
        print(f"[NicknameManager] No permission to change nickname for {member.name}")
        return False
    except discord.HTTPException as e:
        print(f"[NicknameManager] Failed to update nickname for {member.name}: {e}")
        return False
    except Exception as e:
        print(f"[NicknameManager] Error updating nickname for {member.name}: {e}")
        return False
    finally:
        # 봇이 변경 완료 표시
        if hasattr(member.guild.me, '_nickname_update_in_progress'):
            member.guild.me._nickname_update_in_progress.discard(member.id)


async def refresh_all_nicknames(bot):
    """모든 사용자의 닉네임 새로고침 (1시간마다 실행)"""
    while True:
        try:
            await asyncio.sleep(NICKNAME_REFRESH_INTERVAL)
            
            print("[NicknameManager] Starting nickname refresh cycle...")
            
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
                
                # 닉네임 업데이트
                success = await update_user_nickname(member, level)
                if success:
                    updated_count += 1
                else:
                    failed_count += 1
                
                # 티어 역할 동기화 (축하 메시지는 보내지 않음 - 동기화이므로)
                await update_tier_role(member, level)
                
                # API 레이트 리밋 방지를 위해 약간의 딜레이
                await asyncio.sleep(0.1)
            
            print(f"[NicknameManager] Nickname refresh completed: {updated_count} updated, {failed_count} failed")
            
        except Exception as e:
            print(f"[NicknameManager] Error in nickname refresh cycle: {e}")


async def initial_nickname_update(bot):
    """봇 시작 시 모든 사용자의 닉네임을 즉시 업데이트"""
    print("[NicknameManager] Starting initial nickname update...")
    
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
        
        # 닉네임 업데이트
        success = await update_user_nickname(member, level)
        if success:
            updated_count += 1
        else:
            failed_count += 1
        
        # API 레이트 리밋 방지를 위해 약간의 딜레이
        await asyncio.sleep(0.1)
    
    print(f"[NicknameManager] Initial nickname update completed: {updated_count} updated, {failed_count} failed")


def setup_nickname_refresh(bot):
    """닉네임 새로고침 백그라운드 작업 시작"""
    task = asyncio.create_task(refresh_all_nicknames(bot))
    return task


async def check_and_restore_nickname(member: discord.Member, level: int) -> bool:
    """
    닉네임의 레벨 표시가 올바른지 확인하고 필요시 복원
    Returns: 복원 여부 (True: 복원됨, False: 이미 올바름 또는 복원 불가)
    """
    try:
        current_nickname = member.display_name or member.name
        
        # JK 역할 사용자는 운영자 아이콘만 체크
        if has_jk_role(member):
            # JK 역할 사용자는 update_user_nickname에서 처리
            return await update_user_nickname(member, level)
        
        # 레벨 표시 추출
        extracted_level = extract_level_from_nickname(current_nickname)
        
        # 레벨 표시가 없거나 잘못되었으면 복원
        if extracted_level != level:
            return await update_user_nickname(member, level)
        
        # 이미 올바른 레벨 표시가 있으면 스킵
        return False
        
    except Exception as e:
        print(f"[NicknameManager] Error checking nickname for {member.name}: {e}")
        return False


def setup_nickname_update_event(bot):
    """닉네임 변경 이벤트 핸들러 설정"""
    # 봇이 닉네임을 변경 중인지 추적 (무한 루프 방지)
    bot._nickname_update_in_progress = set()
    
    @bot.event
    async def on_member_update(before: discord.Member, after: discord.Member):
        """멤버 정보 업데이트 감지 (닉네임 변경 등)"""
        # 봇은 무시
        if after.bot:
            return
        
        # 닉네임이 변경되었는지 확인
        if before.display_name != after.display_name:
            # 봇이 변경한 경우는 무시 (무한 루프 방지)
            if after.id in bot._nickname_update_in_progress:
                bot._nickname_update_in_progress.discard(after.id)
                return
            
            # 사용자 레벨 조회
            try:
                user = await get_user(after.id, after.guild.id)
                if user:
                    # 레벨 표시 확인 및 복원
                    restored = await check_and_restore_nickname(after, user['level'])
                    if restored:
                        print(f"[NicknameManager] 닉네임 변경 감지 및 레벨 표시 복원: {after.name} (레벨 {user['level']})")
            except Exception as e:
                print(f"[NicknameManager] 닉네임 변경 이벤트 처리 중 오류: {e}")
    
    return bot

