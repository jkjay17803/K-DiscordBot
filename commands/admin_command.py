# commands/admin_command.py - 관리자 전용 명령어

import asyncio
import discord
from discord.ext import commands
from level_system import (
    add_exp, set_current_exp, add_level, set_level,
    add_points, set_points, calculate_required_exp
)
from nickname_manager import update_user_nickname
from logger import send_command_log, send_levelup_log


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
        
        if count > 100:
            await ctx.send("❌ 한 번에 최대 100개까지만 삭제할 수 있습니다.")
            return
        
        try:
            # 최근 메시지 가져오기 (자기 자신의 명령어 메시지 포함)
            deleted = await ctx.channel.purge(limit=count + 1)  # +1은 명령어 메시지 포함
            
            # 삭제 완료 메시지 (자동으로 삭제되도록)
            message = await ctx.send(f"✅ {len(deleted) - 1}개의 메시지가 삭제되었습니다.")
            
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