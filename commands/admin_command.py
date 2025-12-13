# commands/admin_command.py - 관리자 전용 명령어

import discord
from discord.ext import commands
from level_system import add_exp, set_level
from nickname_manager import update_user_nickname
from logger import send_command_log, send_levelup_log


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return any(role.name == "JK" for role in ctx.author.roles)
    return commands.check(predicate)


def get_target_user(ctx, user_input: str):
    """사용자 입력으로부터 대상 사용자 반환"""
    # 멘션 처리
    if ctx.message.mentions:
        return ctx.message.mentions[0]
    
    # "iiii" 처리
    if user_input.lower() == "iiii":
        return ctx.author
    
    # 사용자 ID 처리
    try:
        target_user_id = int(user_input)
        target_user = ctx.guild.get_member(target_user_id)
        if target_user is None:
            return None
        return target_user
    except ValueError:
        return None


def admin_command(k):

    @k.group(name="jk레벨")
    @check_jk()
    async def jk_level_group(ctx):
        """JK 레벨 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk레벨 add @사용자 [exp수치]` 또는 `!jk레벨 set @사용자 [레벨]`")

    @jk_level_group.command(name="add")
    @check_jk()
    async def add_exp_command(ctx, member: discord.Member = None, exp_amount: int = None):
        """
        관리자 전용: 사용자에게 exp를 지급합니다.
        사용법: !jk레벨 add @사용자 [exp수치]
        """
        if member is None or exp_amount is None:
            await ctx.send("❌ 사용법: `!jk레벨 add @사용자 [exp수치]`\n예: `!jk레벨 add @홍길동 100`")
            return
        
        target_user = member
        target_user_id = target_user.id
        guild_id = ctx.guild.id
        
        # 명령어 실행 로그 전송
        await send_command_log(
            ctx.bot,
            ctx.author,
            f"!jk레벨 add @{target_user.display_name} {exp_amount}",
            target_user,
            f"EXP {exp_amount:,} 지급"
        )
        
        # exp 지급
        result = await add_exp(target_user_id, guild_id, exp_amount)
        
        # 레벨업 로그 전송
        if result['leveled_up']:
            await send_levelup_log(
                ctx.bot,
                target_user,
                result['old_level'],
                result['new_level'],
                result['points_earned'],
                result['new_points'],
                "JK 명령어 (EXP 지급)"
            )
        
        # 결과 메시지 생성
        embed = discord.Embed(
            title="EXP 지급",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="대상 사용자",
            value=f"{target_user.display_name} ({target_user.mention})",
            inline=False
        )
        
        embed.add_field(
            name="지급된 EXP",
            value=f"**+{exp_amount:,}**",
            inline=True
        )
        
        embed.add_field(
            name="현재 레벨",
            value=f"**{result['new_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="현재 EXP",
            value=f"{result['new_exp']:,} / {result['required_exp']:,}",
            inline=False
        )
        
        if result['leveled_up']:
            embed.add_field(
                name="레벨업!",
                value=f"🎉 **레벨 {result['new_level']}** 달성!\n포인트 +{result['points_earned']}",
                inline=False
            )
            embed.color = discord.Color.gold()
        
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
        
        # 레벨업 시 닉네임 업데이트
        if result['leveled_up']:
            await update_user_nickname(target_user, result['new_level'])
    
    @jk_level_group.command(name="set")
    @check_jk()
    async def set_level_command(ctx, member: discord.Member = None, target_level: int = None):
        """
        관리자 전용: 사용자의 레벨을 직접 설정합니다.
        사용법: !jk레벨 set @사용자 [레벨]
        """
        if member is None or target_level is None:
            await ctx.send("❌ 사용법: `!jk레벨 set @사용자 [레벨]`\n예: `!jk레벨 set @홍길동 50`")
            return
        
        if target_level < 1:
            await ctx.send("❌ 레벨은 1 이상이어야 합니다.")
            return
        
        target_user = member
        target_user_id = target_user.id
        guild_id = ctx.guild.id
        
        # 명령어 실행 로그 전송
        await send_command_log(
            ctx.bot,
            ctx.author,
            f"!jk레벨 set @{target_user.display_name} {target_level}",
            target_user,
            f"레벨을 {target_level}로 설정"
        )
        
        # 레벨 설정
        result = await set_level(target_user_id, guild_id, target_level)
        
        # 레벨 변경 로그 전송 (레벨이 변경된 경우)
        if result['old_level'] != result['new_level']:
            await send_levelup_log(
                ctx.bot,
                target_user,
                result['old_level'],
                result['new_level'],
                result['points_earned'],
                result['new_points'],
                "JK 명령어 (레벨 설정)"
            )
        
        # 결과 메시지 생성
        embed = discord.Embed(
            title="레벨 설정",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="대상 사용자",
            value=f"{target_user.display_name} ({target_user.mention})",
            inline=False
        )
        
        embed.add_field(
            name="이전 레벨",
            value=f"**{result['old_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="새 레벨",
            value=f"**{result['new_level']}**",
            inline=True
        )
        
        embed.add_field(
            name="현재 EXP",
            value=f"{result['new_exp']:,} / {result['required_exp']:,}",
            inline=False
        )
        
        if result['points_earned'] != 0:
            points_text = f"+{result['points_earned']}" if result['points_earned'] > 0 else str(result['points_earned'])
            embed.add_field(
                name="포인트 변화",
                value=f"**{points_text}** (총 {result['new_points']:,} 포인트)",
                inline=False
            )
        
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
        
        # 닉네임 업데이트
        await update_user_nickname(target_user, result['new_level'])
    
    @add_exp_command.error
    async def add_exp_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법: `!jk레벨 add @사용자 [exp수치]`\n예: `!jk레벨 add @홍길동 100`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ exp 수치는 숫자여야 합니다.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")
    
    @set_level_command.error
    async def set_level_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법: `!jk레벨 set @사용자 [레벨]`\n예: `!jk레벨 set @홍길동 50`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 레벨은 숫자여야 합니다.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

