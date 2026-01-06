# commands/admin_command.py - 관리자 전용 명령어

import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from level_system import (
    add_exp, set_current_exp, add_level, set_level,
    add_points, set_points, calculate_required_exp, get_user_level_info
)
from nickname_manager import update_user_nickname
from role_manager import update_tier_role
from logger import send_command_log, send_levelup_log, send_tier_upgrade_log
from config import VOICE_CHANNEL_EXP


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return any(role.name == "JK" for role in ctx.author.roles)
    return commands.check(predicate)


async def parse_user_id(ctx, user_input):
    """사용자 ID 파싱 - 'i' 입력 시 자기 자신 ID 반환, 숫자면 ID로 사용"""
    if isinstance(user_input, str) and user_input.lower() == 'i':
        return ctx.author.id
    
    # 숫자로 변환 시도 (사용자 ID)
    try:
        user_id = int(user_input)
        return user_id
    except (ValueError, TypeError):
        raise commands.BadArgument("사용자 ID는 숫자여야 합니다. 'i'를 입력하면 자기 자신에게 적용됩니다.")


def admin_command(k):

    # ========== !jk경험치 명령어 그룹 ==========
    @k.group(name="jk경험치")
    @check_jk()
    async def jk_exp_group(ctx):
        """JK 경험치 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk경험치 add @사용자 [exp수치]` 또는 `!jk경험치 set @사용자 [exp수치]`")

    @jk_exp_group.command(name="add")
    @check_jk()
    async def add_exp_command(ctx, user_id_input = None, exp_amount: int = None):
        """경험치 추가"""
        if user_id_input is None or exp_amount is None:
            await ctx.send("❌ 사용법: `!jk경험치 add [사용자ID] [exp수치]` 또는 `!jk경험치 add i [exp수치]`\n예: `!jk경험치 add 123456789012345678 100`")
            return
        
        try:
            target_user_id = await parse_user_id(ctx, user_id_input)
        except commands.BadArgument as e:
            await ctx.send(f"❌ {e}")
            return
        
        guild_id = ctx.guild.id
        
        # 사용자 정보 가져오기 (로깅용)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            # 멤버를 찾을 수 없으면 ID만 사용
            user_display = f"ID: {target_user_id}"
        else:
            user_display = f"{target_user.display_name} ({target_user.mention})"
        
        result = await add_exp(target_user_id, guild_id, exp_amount)
        
        # 상세 정보 생성
        progress_percentage = (result['new_exp'] / result['required_exp'] * 100) if result['required_exp'] > 0 else 100
        details = (
            f"EXP {exp_amount:,} 지급\n"
            f"총 EXP: {result.get('old_total_exp', 0):,} → {result.get('new_total_exp', 0):,}\n"
            f"진행률: {result['new_exp']:,}/{result['required_exp']:,} ({progress_percentage:.1f}%)\n"
            f"총 포인트: {result['new_points']:,}"
        )
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk경험치 add {target_user_id} {exp_amount}",
            target_user, details
        )
        
        if result['leveled_up']:
            if target_user:
                await send_levelup_log(
                    ctx.bot, target_user,
                    result['old_level'], result['new_level'],
                    result['points_earned'], result['new_points'],
                    "JK 명령어 (EXP 추가)"
                )
        
        embed = discord.Embed(title="경험치 추가", color=discord.Color.green())
        embed.add_field(name="대상 사용자", value=user_display, inline=False)
        embed.add_field(name="추가된 EXP", value=f"**+{exp_amount:,}**", inline=True)
        embed.add_field(name="현재 레벨", value=f"**{result['new_level']}**", inline=True)
        embed.add_field(name="현재 EXP", value=f"{result['new_exp']:,} / {result['required_exp']:,}", inline=False)
        
        if result['leveled_up']:
            embed.add_field(name="레벨업!", value=f"🎉 **레벨 {result['new_level']}** 달성!\n포인트 +{result['points_earned']}", inline=False)
            embed.color = discord.Color.gold()
        
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)
        
        if result['leveled_up'] and target_user:
            await update_user_nickname(target_user, result['new_level'])
            success, old_tier, new_tier = await update_tier_role(target_user, result['new_level'])
            # 티어 업그레이드 축하 메시지 전송
            if success and old_tier and new_tier and old_tier != new_tier:
                await send_tier_upgrade_log(ctx.bot, target_user, old_tier, new_tier, result['new_level'])

    @jk_exp_group.command(name="set")
    @check_jk()
    async def set_exp_command(ctx, user_id_input = None, exp_amount: int = None):
        """현재 레벨의 경험치 진행률 설정"""
        if user_id_input is None or exp_amount is None:
            await ctx.send("❌ 사용법: `!jk경험치 set [사용자ID] [exp수치]` 또는 `!jk경험치 set i [exp수치]`\n예: `!jk경험치 set 123456789012345678 50`")
            return
        
        if exp_amount < 0:
            await ctx.send("❌ 경험치는 0 이상이어야 합니다.")
            return
        
        try:
            target_user_id = await parse_user_id(ctx, user_id_input)
        except commands.BadArgument as e:
            await ctx.send(f"❌ {e}")
            return
        
        guild_id = ctx.guild.id
        
        # 사용자 정보 가져오기 (로깅용)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            user_display = f"ID: {target_user_id}"
        else:
            user_display = f"{target_user.display_name} ({target_user.mention})"
        
        result = await set_current_exp(target_user_id, guild_id, exp_amount)
        
        # 상세 정보 생성
        progress_percentage = (result['new_exp'] / result['required_exp'] * 100) if result['required_exp'] > 0 else 100
        details = (
            f"현재 레벨의 EXP를 {exp_amount:,}로 설정\n"
            f"총 EXP: {result['old_total_exp']:,} → {result['new_total_exp']:,}\n"
            f"진행률: {result['new_exp']:,}/{result['required_exp']:,} ({progress_percentage:.1f}%)\n"
            f"총 포인트: {result['new_points']:,}"
        )
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk경험치 set {target_user_id} {exp_amount}",
            target_user, details
        )
        
        if result['old_level'] != result['new_level']:
            if target_user:
                await send_levelup_log(
                    ctx.bot, target_user,
                    result['old_level'], result['new_level'],
                    result['points_earned'], result['new_points'],
                    "JK 명령어 (EXP 설정)"
                )
        
        embed = discord.Embed(title="경험치 설정", color=discord.Color.blue())
        embed.add_field(name="대상 사용자", value=user_display, inline=False)
        embed.add_field(name="이전 EXP", value=f"**{result['old_exp']:,}** / {calculate_required_exp(result['old_level']):,}", inline=True)
        embed.add_field(name="새 EXP", value=f"**{result['new_exp']:,}** / {result['required_exp']:,}", inline=True)
        
        if result['old_level'] != result['new_level']:
            embed.add_field(name="레벨 변화", value=f"**{result['old_level']}** → **{result['new_level']}**", inline=False)
        
        if result['points_earned'] != 0:
            points_text = f"+{result['points_earned']}" if result['points_earned'] > 0 else str(result['points_earned'])
            embed.add_field(name="포인트 변화", value=f"**{points_text}** (총 {result['new_points']:,} 포인트)", inline=False)
        
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)
        
        if target_user:
            await update_user_nickname(target_user, result['new_level'])
            if result['old_level'] != result['new_level']:
                success, old_tier, new_tier = await update_tier_role(target_user, result['new_level'])
                # 티어 업그레이드 축하 메시지 전송
                if success and old_tier and new_tier and old_tier != new_tier:
                    await send_tier_upgrade_log(ctx.bot, target_user, old_tier, new_tier, result['new_level'])

    # ========== !jk레벨 명령어 그룹 ==========
    @k.group(name="jk레벨")
    @check_jk()
    async def jk_level_group(ctx):
        """JK 레벨 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk레벨 add [사용자ID] [레벨수]` 또는 `!jk레벨 set [사용자ID] [레벨]`")

    @jk_level_group.command(name="add")
    @check_jk()
    async def add_level_command(ctx, user_id_input = None, levels: int = None):
        """레벨 추가"""
        if user_id_input is None or levels is None:
            await ctx.send("❌ 사용법: `!jk레벨 add [사용자ID] [레벨수]` 또는 `!jk레벨 add i [레벨수]`\n예: `!jk레벨 add 123456789012345678 5`")
            return
        
        try:
            target_user_id = await parse_user_id(ctx, user_id_input)
        except commands.BadArgument as e:
            await ctx.send(f"❌ {e}")
            return
        
        guild_id = ctx.guild.id
        
        # 사용자 정보 가져오기 (로깅용)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            user_display = f"ID: {target_user_id}"
        else:
            user_display = f"{target_user.display_name} ({target_user.mention})"
        
        result = await add_level(target_user_id, guild_id, levels)
        
        # 상세 정보 생성
        progress_percentage = (result['new_exp'] / result['required_exp'] * 100) if result['required_exp'] > 0 else 100
        details = (
            f"레벨 {levels:+d} 추가\n"
            f"총 EXP: {result['old_total_exp']:,} → {result['new_total_exp']:,}\n"
            f"진행률: {result['new_exp']:,}/{result['required_exp']:,} ({progress_percentage:.1f}%)\n"
            f"총 포인트: {result['new_points']:,}"
        )
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk레벨 add {target_user_id} {levels}",
            target_user, details
        )
        
        if result['old_level'] != result['new_level']:
            if target_user:
                await send_levelup_log(
                    ctx.bot, target_user,
                    result['old_level'], result['new_level'],
                    result['points_earned'], result['new_points'],
                    "JK 명령어 (레벨 추가)"
                )
        
        embed = discord.Embed(title="레벨 추가", color=discord.Color.green())
        embed.add_field(name="대상 사용자", value=user_display, inline=False)
        embed.add_field(name="추가된 레벨", value=f"**{levels:+d}**", inline=True)
        embed.add_field(name="이전 레벨", value=f"**{result['old_level']}**", inline=True)
        embed.add_field(name="새 레벨", value=f"**{result['new_level']}**", inline=True)
        embed.add_field(name="현재 EXP", value=f"{result['new_exp']:,} / {result['required_exp']:,}", inline=False)
        
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)
        
        if target_user:
            await update_user_nickname(target_user, result['new_level'])
            if result['old_level'] != result['new_level']:
                success, old_tier, new_tier = await update_tier_role(target_user, result['new_level'])
                # 티어 업그레이드 축하 메시지 전송
                if success and old_tier and new_tier and old_tier != new_tier:
                    await send_tier_upgrade_log(ctx.bot, target_user, old_tier, new_tier, result['new_level'])

    @jk_level_group.command(name="set")
    @check_jk()
    async def set_level_command(ctx, user_id_input = None, target_level: int = None):
        """레벨 설정"""
        if user_id_input is None or target_level is None:
            await ctx.send("❌ 사용법: `!jk레벨 set [사용자ID] [레벨]` 또는 `!jk레벨 set i [레벨]`\n예: `!jk레벨 set 123456789012345678 50`")
            return
        
        if target_level < 1:
            await ctx.send("❌ 레벨은 1 이상이어야 합니다.")
            return
        
        try:
            target_user_id = await parse_user_id(ctx, user_id_input)
        except commands.BadArgument as e:
            await ctx.send(f"❌ {e}")
            return
        
        guild_id = ctx.guild.id
        
        # 사용자 정보 가져오기 (로깅용)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            user_display = f"ID: {target_user_id}"
        else:
            user_display = f"{target_user.display_name} ({target_user.mention})"
        
        result = await set_level(target_user_id, guild_id, target_level)
        
        # 상세 정보 생성
        progress_percentage = (result['new_exp'] / result['required_exp'] * 100) if result['required_exp'] > 0 else 100
        details = (
            f"레벨을 {target_level}로 설정\n"
            f"총 EXP: {result['old_total_exp']:,} → {result['new_total_exp']:,}\n"
            f"진행률: {result['new_exp']:,}/{result['required_exp']:,} ({progress_percentage:.1f}%)\n"
            f"총 포인트: {result['new_points']:,}"
        )
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk레벨 set {target_user_id} {target_level}",
            target_user, details
        )
        
        if result['old_level'] != result['new_level']:
            if target_user:
                await send_levelup_log(
                    ctx.bot, target_user,
                    result['old_level'], result['new_level'],
                    result['points_earned'], result['new_points'],
                    "JK 명령어 (레벨 설정)"
                )
        
        embed = discord.Embed(title="레벨 설정", color=discord.Color.blue())
        embed.add_field(name="대상 사용자", value=user_display, inline=False)
        embed.add_field(name="이전 레벨", value=f"**{result['old_level']}**", inline=True)
        embed.add_field(name="새 레벨", value=f"**{result['new_level']}**", inline=True)
        embed.add_field(name="현재 EXP", value=f"{result['new_exp']:,} / {result['required_exp']:,}", inline=False)
        
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)
        
        if target_user:
            await update_user_nickname(target_user, result['new_level'])
            if result['old_level'] != result['new_level']:
                success, old_tier, new_tier = await update_tier_role(target_user, result['new_level'])
                # 티어 업그레이드 축하 메시지 전송
                if success and old_tier and new_tier and old_tier != new_tier:
                    await send_tier_upgrade_log(ctx.bot, target_user, old_tier, new_tier, result['new_level'])

    # ========== !jk포인트 명령어 그룹 ==========
    @k.group(name="jk포인트")
    @check_jk()
    async def jk_points_group(ctx):
        """JK 포인트 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk포인트 add [사용자ID] [포인트수]` 또는 `!jk포인트 set [사용자ID] [포인트]`")

    @jk_points_group.command(name="add")
    @check_jk()
    async def add_points_command(ctx, user_id_input = None, points_amount: int = None):
        """포인트 추가"""
        if user_id_input is None or points_amount is None:
            await ctx.send("❌ 사용법: `!jk포인트 add [사용자ID] [포인트수]` 또는 `!jk포인트 add i [포인트수]`\n예: `!jk포인트 add 123456789012345678 100`")
            return
        
        try:
            target_user_id = await parse_user_id(ctx, user_id_input)
        except commands.BadArgument as e:
            await ctx.send(f"❌ {e}")
            return
        
        guild_id = ctx.guild.id
        
        # 사용자 정보 가져오기 (로깅용)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            user_display = f"ID: {target_user_id}"
        else:
            user_display = f"{target_user.display_name} ({target_user.mention})"
        
        result = await add_points(target_user_id, guild_id, points_amount)
        
        # 상세 정보 생성
        details = (
            f"포인트 {points_amount:,} 지급\n"
            f"총 포인트: {result['old_points']:,} → {result['new_points']:,}"
        )
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk포인트 add {target_user_id} {points_amount}",
            target_user, details
        )
        
        embed = discord.Embed(title="포인트 추가", color=discord.Color.green())
        embed.add_field(name="대상 사용자", value=user_display, inline=False)
        embed.add_field(name="추가된 포인트", value=f"**{points_amount:+,}**", inline=True)
        embed.add_field(name="이전 포인트", value=f"**{result['old_points']:,}**", inline=True)
        embed.add_field(name="새 포인트", value=f"**{result['new_points']:,}**", inline=True)
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @jk_points_group.command(name="set")
    @check_jk()
    async def set_points_command(ctx, user_id_input = None, target_points: int = None):
        """포인트 설정"""
        if user_id_input is None or target_points is None:
            await ctx.send("❌ 사용법: `!jk포인트 set [사용자ID] [포인트]` 또는 `!jk포인트 set i [포인트]`\n예: `!jk포인트 set 123456789012345678 1000`")
            return
        
        if target_points < 0:
            await ctx.send("❌ 포인트는 0 이상이어야 합니다.")
            return
        
        try:
            target_user_id = await parse_user_id(ctx, user_id_input)
        except commands.BadArgument as e:
            await ctx.send(f"❌ {e}")
            return
        
        guild_id = ctx.guild.id
        
        # 사용자 정보 가져오기 (로깅용)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            user_display = f"ID: {target_user_id}"
        else:
            user_display = f"{target_user.display_name} ({target_user.mention})"
        
        result = await set_points(target_user_id, guild_id, target_points)
        
        # 상세 정보 생성
        details = (
            f"포인트를 {target_points:,}로 설정\n"
            f"총 포인트: {result['old_points']:,} → {result['new_points']:,}"
        )
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk포인트 set {target_user_id} {target_points}",
            target_user, details
        )
        
        embed = discord.Embed(title="포인트 설정", color=discord.Color.blue())
        embed.add_field(name="대상 사용자", value=user_display, inline=False)
        embed.add_field(name="이전 포인트", value=f"**{result['old_points']:,}**", inline=True)
        embed.add_field(name="새 포인트", value=f"**{result['new_points']:,}**", inline=True)
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ========== !jk마켓토글 명령어 ==========
    @k.command(name="jk마켓토글")
    @check_jk()
    async def toggle_market(ctx):
        """마켓 명령어 활성화/비활성화"""
        from database import get_market_enabled, set_market_enabled
        
        guild_id = ctx.guild.id
        current_status = await get_market_enabled(guild_id)
        new_status = not current_status
        
        await set_market_enabled(guild_id, new_status)
        
        # 상세 정보 생성
        status_text = "활성화" if new_status else "비활성화"
        details = f"마켓 명령어를 {status_text}했습니다."
        
        await send_command_log(
            ctx.bot, ctx.author,
            f"!jk마켓토글",
            None, details
        )
        
        embed = discord.Embed(
            title="마켓 토글",
            color=discord.Color.green() if new_status else discord.Color.red()
        )
        embed.add_field(
            name="상태",
            value=f"**{'✅ 활성화' if new_status else '❌ 비활성화'}**",
            inline=False
        )
        embed.add_field(
            name="설명",
            value=(
                "활성화: `!마켓`, `!구매`, `!티켓목록` 명령어 사용 가능\n"
                "비활성화: 마켓 명령어 사용 불가"
            ),
            inline=False
        )
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ========== !jk메시지 명령어 ==========
    @k.command(name="jk메시지")
    @check_jk()
    async def copy_message(ctx, channel_id: int = None):
        """바로 위 메시지를 지정된 채널로 복사"""
        if channel_id is None:
            await ctx.send("❌ 사용법: `!jk메시지 [채널ID]`\n예: `!jk메시지 123456789012345678`")
            return
        
        try:
            # 바로 위 메시지 가져오기 (자기 자신의 명령어 메시지 제외)
            messages = [msg async for msg in ctx.channel.history(limit=2)]
            if len(messages) < 2:
                await ctx.send("❌ 복사할 메시지가 없습니다.")
                return
            
            target_msg = messages[1]  # 명령어 메시지 바로 위 메시지
            
            # 대상 채널 찾기
            target_channel = ctx.bot.get_channel(channel_id)
            if target_channel is None:
                await ctx.send(f"❌ 채널을 찾을 수 없습니다. 채널 ID `{channel_id}`를 확인해주세요.")
                return
            
            # 메시지 복사 (임베드, 파일 등 포함)
            files = []
            if target_msg.attachments:
                for attachment in target_msg.attachments:
                    file = await attachment.to_file()
                    files.append(file)
            
            # 임베드가 있으면 임베드도 복사
            if target_msg.embeds:
                for embed in target_msg.embeds:
                    await target_channel.send(content=target_msg.content, embed=embed, files=files if files else None)
            else:
                # 일반 메시지 또는 파일만 있는 경우
                if target_msg.content or files:
                    await target_channel.send(content=target_msg.content, files=files if files else None)
                else:
                    await ctx.send("❌ 복사할 내용이 없습니다.")
                    return
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 메시지 복사 완료",
                color=discord.Color.green()
            )
            embed.add_field(
                name="출발 채널",
                value=f"{ctx.channel.mention}",
                inline=True
            )
            embed.add_field(
                name="도착 채널",
                value=f"{target_channel.mention}",
                inline=True
            )
            embed.add_field(
                name="원본 메시지",
                value=f"[메시지로 이동]({target_msg.jump_url})" if target_msg.jump_url else "링크 없음",
                inline=False
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
            # 로그 기록
            await send_command_log(
                ctx.bot, ctx.author,
                f"!jk메시지 {channel_id}",
                None,
                f"메시지를 {ctx.channel.mention}에서 {target_channel.mention}로 복사"
            )
            
        except discord.Forbidden:
            await ctx.send("❌ 해당 채널에 메시지를 보낼 권한이 없습니다.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ 메시지 전송 중 오류가 발생했습니다: {e}")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")

    # ========== !jk클리어 명령어 ==========
    @k.command(name="jk클리어")
    @check_jk()
    async def clear_messages(ctx, count: int = None):
        """메시지 삭제"""
        if count is None:
            await ctx.send("❌ 사용법: `!jk클리어 [줄 개수]`\n예: `!jk클리어 10`")
            return
        
        if count < 1:
            await ctx.send("❌ 1 이상의 숫자를 입력해주세요.")
            return
        
        if count > 500:
            await ctx.send("❌ 한 번에 최대 500개까지만 삭제할 수 있습니다.")
            return
        
        try:
            total_deleted = 0
            remaining = count
            is_first_batch = True
            
            # Discord API 제한(한 번에 100개)을 고려하여 여러 번 호출
            while remaining > 0:
                # 한 번에 삭제할 개수 (최대 100개)
                batch_size = min(remaining, 100)
                # 명령어 메시지도 포함하여 삭제 (첫 번째 호출에만)
                limit = batch_size + 1 if is_first_batch else batch_size
                
                deleted = await ctx.channel.purge(limit=limit)
                
                if len(deleted) == 0:
                    break
                
                # 첫 번째 배치에서는 명령어 메시지 제외
                if is_first_batch:
                    deleted_count = len(deleted) - 1
                    is_first_batch = False
                else:
                    deleted_count = len(deleted)
                
                total_deleted += deleted_count
                remaining -= deleted_count
                
                # 더 이상 삭제할 메시지가 없으면 종료
                if deleted_count == 0:
                    break
                
                # API 제한을 피하기 위해 짧은 대기
                if remaining > 0:
                    await asyncio.sleep(0.5)
            
            # 삭제 완료 메시지
            message = await ctx.send(f"✅ {total_deleted}개의 메시지가 삭제되었습니다.")
            
            # # 3초 후 삭제 완료 메시지도 삭제
            # await asyncio.sleep(3)
            # try:
            #     await message.delete()
            # except:
            #     pass
                
        except discord.Forbidden:
            await ctx.send("❌ 메시지를 삭제할 권한이 없습니다.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ 메시지 삭제 중 오류가 발생했습니다: {e}")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")

    # ========== !jk디버그 명령어 그룹 ==========
    @k.group(name="jk디버그")
    @check_jk()
    async def jk_debug_group(ctx):
        """JK 디버그 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk디버그 경험치` 또는 `!jk디버그 참여`")

    @jk_debug_group.command(name="경험치")
    @check_jk()
    async def debug_exp_command(ctx):
        """현재 시간대에 경험치 획득 가능 여부 확인"""
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # 시간 체크: 06:00 ~ 23:59 사이만 경험치 지급
        can_earn_exp = 6 <= current_hour < 24
        
        embed = discord.Embed(
            title="🔍 경험치 획득 시간 체크",
            color=discord.Color.green() if can_earn_exp else discord.Color.red(),
            timestamp=datetime.now()
        )
        
        time_str = f"{current_hour:02d}:{current_minute:02d}"
        status = "✅ 획득 가능" if can_earn_exp else "❌ 획득 불가"
        time_range = "06:00 ~ 23:59"
        
        embed.add_field(
            name="현재 시간",
            value=time_str,
            inline=True
        )
        
        embed.add_field(
            name="상태",
            value=status,
            inline=True
        )
        
        embed.add_field(
            name="경험치 획득 가능 시간",
            value=time_range,
            inline=False
        )
        
        await ctx.send(embed=embed)

    @jk_debug_group.command(name="참여")
    @check_jk()
    async def debug_participants_command(ctx):
        """EXP 획득 가능한 각 음성채널의 참여자 목록 및 세션 정보"""
        if not VOICE_CHANNEL_EXP:
            await ctx.send("❌ EXP 지급 채널이 설정되지 않았습니다.")
            return
        
        # voice_monitor 인스턴스 가져오기
        if not hasattr(ctx.bot, 'voice_monitor') or ctx.bot.voice_monitor is None:
            await ctx.send("❌ Voice monitor가 초기화되지 않았습니다.")
            return
        
        voice_monitor = ctx.bot.voice_monitor
        active_sessions = voice_monitor.active_sessions
        
        embed = discord.Embed(
            title="🔍 음성채널 참여자 현황",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        has_participants = False
        
        for channel_id, exp_settings in VOICE_CHANNEL_EXP.items():
            channel = ctx.guild.get_channel(channel_id)
            
            if channel is None:
                embed.add_field(
                    name=f"❌ 채널을 찾을 수 없음 (ID: {channel_id})",
                    value=f"지급 설정: {exp_settings[0]}분마다 {exp_settings[1]} EXP",
                    inline=False
                )
                continue
            
            # 봇 제외한 멤버만 가져오기
            members = [m for m in channel.members if not m.bot]
            
            if members:
                has_participants = True
                
                # 각 멤버의 세션 정보 수집
                member_details = []
                for member in members:
                    user_id = member.id
                    guild_id = ctx.guild.id
                    
                    # 세션 정보 가져오기
                    session_info = active_sessions.get(user_id)
                    if session_info and session_info['channel_id'] == channel_id:
                        join_time = session_info['join_time']
                        exp_interval = session_info['exp_interval']
                        exp_amount = session_info['exp_amount']
                        
                        # 머문 시간 계산
                        current_time = datetime.now()
                        duration = current_time - join_time
                        duration_minutes = int(duration.total_seconds() / 60)
                        duration_hours = duration_minutes // 60
                        duration_mins = duration_minutes % 60
                        
                        # 이번 세션에서 얻은 EXP 계산 (시간 제한 06:00 ~ 23:59 고려)
                        session_exp_earned = 0
                        check_time = join_time + timedelta(minutes=exp_interval)  # 첫 지급은 join_time + exp_interval 후
                        exp_interval_delta = timedelta(minutes=exp_interval)
                        
                        while check_time <= current_time:
                            check_hour = check_time.hour
                            # 시간 제한 내에 있는지 확인
                            if 6 <= check_hour < 24:
                                session_exp_earned += exp_amount
                            check_time += exp_interval_delta
                        
                        # 시간 표시 형식 (시간이 있으면 시간 포함, 없으면 분만)
                        if duration_hours > 0:
                            duration_str = f"{duration_hours}시간 {duration_mins}분"
                        else:
                            duration_str = f"{duration_mins}분"
                        
                        member_details.append(
                            f"{member.display_name}: {duration_str} / {session_exp_earned}exp"
                        )
                    else:
                        # 세션 정보가 없는 경우 (세션이 시작되지 않았거나 다른 채널의 세션)
                        member_details.append(
                            f"{member.display_name}: 0분 / 0exp"
                        )
                
                member_list = "\n".join(member_details)
                field_value = f"⏱️ 머문 시간 / ⭐ 이번 세션 EXP\n{member_list}\n(설정: {exp_settings[0]}분마다 {exp_settings[1]} EXP)"
                
                embed.add_field(
                    name=f"🎤 {channel.name} ({len(members)}명)",
                    value=field_value,
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"🎤 {channel.name} (0명)",
                    value=f"⏱️ 머문 시간 / ⭐ 이번 세션 EXP\n참여자 없음\n(설정: {exp_settings[0]}분마다 {exp_settings[1]} EXP)",
                    inline=False
                )
        
        if not has_participants:
            embed.add_field(
                name="정보",
                value="현재 EXP 지급 채널에 참여자가 없습니다.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @jk_debug_group.error
    async def jk_debug_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

    # ========== 에러 핸들러 ==========
    @add_exp_command.error
    @set_exp_command.error
    @add_level_command.error
    @set_level_command.error
    @add_points_command.error
    @set_points_command.error
    async def admin_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 숫자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")
    
    @copy_message.error
    async def copy_message_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법: `!jk메시지 [채널ID]`\n예: `!jk메시지 123456789012345678`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 채널 ID를 올바르게 입력해주세요. (숫자만 입력)")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")
    
    @clear_messages.error
    async def clear_messages_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법: `!jk클리어 [줄 개수]`\n예: `!jk클리어 10`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 숫자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")