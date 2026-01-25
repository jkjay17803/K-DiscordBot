# commands/level_system_command.py - JK 레벨 시스템 설정 명령어

import discord
from discord.ext import commands
from datetime import datetime
from level_ranges_manager import (
    load_level_ranges, add_level_range, remove_level_ranges_by_range,
    update_level_range, save_level_ranges
)
from utils import has_jk_role


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


def level_system_command(k):

    # ========== !jk레벨시스템 명령어 그룹 ==========
    @k.group(name="jk레벨시스템")
    @check_jk()
    async def jk_level_system_group(ctx):
        """JK 레벨 시스템 설정 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk레벨시스템 리스트` 또는 `!jk레벨시스템 set [n]:[m] [N] [M]` 또는 `!jk레벨시스템 remove [n]~[m]`")

    @jk_level_system_group.command(name="리스트")
    @check_jk()
    async def level_system_list_command(ctx):
        """레벨 시스템 설정 목록 조회"""
        try:
            ranges = load_level_ranges()
            
            if not ranges:
                await ctx.send("❌ 등록된 레벨 범위 설정이 없습니다.")
                return
            
            # 시작 레벨 순으로 정렬
            sorted_ranges = sorted(ranges.items(), key=lambda x: x[0][0])
            
            # 메시지 생성
            message_lines = []
            for (start, end), (minutes, points) in sorted_ranges:
                message_lines.append(f"{start}~{end}레벨 : {minutes}분, {points}포인트")
            
            message = "\n".join(message_lines)
            
            embed = discord.Embed(
                title="📋 레벨 시스템 설정 목록",
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"총 {len(ranges)}개의 레벨 범위 설정")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_level_system_group.command(name="set")
    @check_jk()
    async def level_system_set_command(ctx, range_str: str = None, minutes: int = None, points: int = None):
        """레벨 범위 설정 추가/수정"""
        if range_str is None or minutes is None or points is None:
            await ctx.send("❌ 사용법: `!jk레벨시스템 set [n]:[m] [N] [M]`\n예: `!jk레벨시스템 set 1:10 10 10` (1~10레벨: 10분, 10포인트)")
            return
        
        # n:m 형식 파싱
        if ':' not in range_str:
            await ctx.send("❌ 형식이 올바르지 않습니다. `n:m` 형식으로 입력해주세요.\n예: `1:10` (1~10레벨)")
            return
        
        try:
            parts = range_str.split(':', 1)
            start = int(parts[0].strip())
            end = int(parts[1].strip())
        except ValueError:
            await ctx.send("❌ 레벨 범위는 숫자여야 합니다.")
            return
        
        if start < 1 or end < 1:
            await ctx.send("❌ 레벨은 1 이상이어야 합니다.")
            return
        
        if start > end:
            await ctx.send("❌ 시작 레벨이 끝 레벨보다 클 수 없습니다.")
            return
        
        if minutes < 1 or points < 1:
            await ctx.send("❌ 시간과 포인트는 1 이상이어야 합니다.")
            return
        
        try:
            # 기존 범위 확인
            existing_ranges = load_level_ranges()
            overlapping = []
            for (existing_start, existing_end), (existing_minutes, existing_points) in existing_ranges.items():
                # 범위가 겹치는지 확인
                if existing_start <= end and existing_end >= start:
                    overlapping.append((existing_start, existing_end, existing_minutes, existing_points))
            
            # 겹치는 범위가 있으면 업데이트 (제거 후 추가)
            if overlapping:
                # 겹치는 범위 제거
                removed = remove_level_ranges_by_range(start, end)
                # 새 범위 추가
                success = add_level_range(start, end, minutes, points)
                action = "업데이트"
                removed_info = "\n".join([f"- {s}~{e}레벨: {m}분, {p}포인트" for s, e, m, p in removed])
            else:
                # 새 범위 추가
                success = add_level_range(start, end, minutes, points)
                action = "추가"
                removed_info = "없음"
            
            if not success:
                await ctx.send(f"❌ 설정 {action}에 실패했습니다.")
                return
            
            embed = discord.Embed(
                title=f"✅ 레벨 범위 설정 {action} 완료",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="레벨 범위",
                value=f"**{start}~{end}레벨**",
                inline=False
            )
            embed.add_field(
                name="레벨업 시간",
                value=f"**{minutes}분**",
                inline=True
            )
            embed.add_field(
                name="레벨업 포인트",
                value=f"**{points}포인트**",
                inline=True
            )
            if overlapping:
                embed.add_field(
                    name="제거된 겹치는 범위",
                    value=removed_info if removed_info != "없음" else "없음",
                    inline=False
                )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_level_system_group.command(name="remove")
    @check_jk()
    async def level_system_remove_command(ctx, range_str: str = None):
        """레벨 범위 설정 제거"""
        if range_str is None:
            await ctx.send("❌ 사용법: `!jk레벨시스템 remove [n]~[m]`\n예: `!jk레벨시스템 remove 100~120`")
            return
        
        # n~m 형식 파싱
        if '~' not in range_str:
            await ctx.send("❌ 형식이 올바르지 않습니다. `n~m` 형식으로 입력해주세요.\n예: `100~120` (100~120레벨 범위)")
            return
        
        try:
            parts = range_str.split('~', 1)
            start = int(parts[0].strip())
            end = int(parts[1].strip())
        except ValueError:
            await ctx.send("❌ 레벨 범위는 숫자여야 합니다.")
            return
        
        if start < 1 or end < 1:
            await ctx.send("❌ 레벨은 1 이상이어야 합니다.")
            return
        
        if start > end:
            await ctx.send("❌ 시작 레벨이 끝 레벨보다 클 수 없습니다.")
            return
        
        try:
            # 제거할 범위 확인
            existing_ranges = load_level_ranges()
            overlapping = []
            for (existing_start, existing_end), (existing_minutes, existing_points) in existing_ranges.items():
                # 범위가 겹치는지 확인
                if existing_start <= end and existing_end >= start:
                    overlapping.append((existing_start, existing_end, existing_minutes, existing_points))
            
            if not overlapping:
                await ctx.send(f"❌ {start}~{end}레벨 범위와 겹치는 설정이 없습니다.")
                return
            
            # 제거
            removed = remove_level_ranges_by_range(start, end)
            
            if not removed:
                await ctx.send(f"❌ 설정 제거에 실패했습니다.")
                return
            
            # 삭제된 내역 정보 생성
            removed_info = "\n".join([f"{s}~{e}레벨: {m}분, {p}포인트" for s, e, m, p in removed])
            
            embed = discord.Embed(
                title="✅ 레벨 범위 설정 제거 완료",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="제거 대상 범위",
                value=f"**{start}~{end}레벨**",
                inline=False
            )
            embed.add_field(
                name="삭제된 레벨 범위 설정",
                value=removed_info,
                inline=False
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name} | 총 {len(removed)}개 제거")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_level_system_group.command(name="add")
    @check_jk()
    async def level_system_add_command(ctx, range_str: str = None, minutes: int = None, points: int = None):
        """레벨 범위 설정 추가/수정 (set의 별칭)"""
        # set 명령어와 동일한 로직 사용
        await level_system_set_command(ctx, range_str, minutes, points)

    # ========== 에러 핸들러 ==========
    @level_system_list_command.error
    @level_system_set_command.error
    @level_system_add_command.error
    @level_system_remove_command.error
    async def level_system_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 인자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

