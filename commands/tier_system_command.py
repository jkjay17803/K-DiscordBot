# commands/tier_system_command.py - JK 티어 시스템 설정 명령어

import discord
from discord.ext import commands
from datetime import datetime
from tier_roles_manager import (
    load_tier_roles, add_tier_role, remove_tier_role,
    update_tier_role, save_tier_roles
)
from utils import has_jk_role


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


def tier_system_command(k):

    # ========== !jk티어시스템 명령어 그룹 ==========
    @k.group(name="jk티어시스템")
    @check_jk()
    async def jk_tier_system_group(ctx):
        """JK 티어 시스템 설정 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk티어시스템 리스트` 또는 `!jk티어시스템 set [티어이름] [레벨] [역할이름]` 또는 `!jk티어시스템 remove [티어이름]`")

    @jk_tier_system_group.command(name="리스트")
    @check_jk()
    async def tier_system_list_command(ctx):
        """티어 시스템 설정 목록 조회"""
        try:
            roles = load_tier_roles()
            
            if not roles:
                await ctx.send("❌ 등록된 티어 역할 설정이 없습니다.")
                return
            
            # 레벨 순으로 정렬 (높은 레벨부터)
            sorted_roles = sorted(roles.items(), key=lambda x: x[1][0], reverse=True)
            
            # 메시지 생성
            message_lines = []
            for tier_name, (required_level, role_name) in sorted_roles:
                message_lines.append(f"{tier_name}: 레벨 {required_level} 이상 → {role_name} 역할")
            
            message = "\n".join(message_lines)
            
            embed = discord.Embed(
                title="📋 티어 시스템 설정 목록",
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"총 {len(roles)}개의 티어 설정")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_tier_system_group.command(name="set")
    @check_jk()
    async def tier_system_set_command(ctx, tier_name: str = None, required_level: int = None, role_name: str = None):
        """티어 역할 설정 추가/수정"""
        if tier_name is None or required_level is None or role_name is None:
            await ctx.send("❌ 사용법: `!jk티어시스템 set [티어이름] [레벨] [역할이름]`\n예: `!jk티어시스템 set 브론즈 0 Bronze` (레벨 0 이상 → Bronze 역할)")
            return
        
        if required_level < 0:
            await ctx.send("❌ 레벨은 0 이상이어야 합니다.")
            return
        
        try:
            # 기존 설정 확인
            existing_roles = load_tier_roles()
            is_update = tier_name in existing_roles
            
            # 설정 추가/업데이트
            success = add_tier_role(tier_name, required_level, role_name)
            
            if not success:
                await ctx.send(f"❌ 설정 {'업데이트' if is_update else '추가'}에 실패했습니다.")
                return
            
            action = "업데이트" if is_update else "추가"
            old_info = ""
            if is_update:
                old_required_level, old_role_name = existing_roles[tier_name]
                old_info = f"\n**이전 설정:** 레벨 {old_required_level} 이상 → {old_role_name} 역할"
            
            embed = discord.Embed(
                title=f"✅ 티어 역할 설정 {action} 완료",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="티어 이름",
                value=f"**{tier_name}**",
                inline=False
            )
            embed.add_field(
                name="도달 레벨",
                value=f"**레벨 {required_level} 이상**",
                inline=True
            )
            embed.add_field(
                name="역할 이름",
                value=f"**{role_name}**",
                inline=True
            )
            if old_info:
                embed.add_field(
                    name="변경 내역",
                    value=old_info,
                    inline=False
                )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_tier_system_group.command(name="remove")
    @check_jk()
    async def tier_system_remove_command(ctx, tier_name: str = None):
        """티어 역할 설정 제거"""
        if tier_name is None:
            await ctx.send("❌ 사용법: `!jk티어시스템 remove [티어이름]`\n예: `!jk티어시스템 remove 브론즈`")
            return
        
        try:
            # 제거할 설정 확인
            existing_roles = load_tier_roles()
            
            if tier_name not in existing_roles:
                await ctx.send(f"❌ `{tier_name}` 티어 설정이 없습니다.")
                return
            
            # 제거
            removed = remove_tier_role(tier_name)
            
            if removed is None:
                await ctx.send(f"❌ 설정 제거에 실패했습니다.")
                return
            
            removed_level, removed_role = removed
            
            embed = discord.Embed(
                title="✅ 티어 역할 설정 제거 완료",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="제거된 티어",
                value=f"**{tier_name}**",
                inline=False
            )
            embed.add_field(
                name="삭제된 설정",
                value=f"레벨 {removed_level} 이상 → {removed_role} 역할",
                inline=False
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== 에러 핸들러 ==========
    @tier_system_list_command.error
    @tier_system_set_command.error
    @tier_system_remove_command.error
    async def tier_system_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 인자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

