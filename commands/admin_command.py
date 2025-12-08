# commands/admin_command.py - 관리자 전용 명령어

import discord
from discord.ext import commands
from level_system import add_exp
from nickname_manager import update_user_nickname


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return any(role.name == "JK" for role in ctx.author.roles)
    return commands.check(predicate)


def admin_command(k):

    @k.command(name="레벨업")
    @check_jk()
    async def level_up_user(ctx, user_id: str, exp_amount: int):
        """
        관리자 전용: 사용자에게 exp를 지급합니다.
        사용법: !레벨업 [사용자_id] [exp수치]
        사용자_id를 "iiii"로 입력하면 명령어를 사용한 사람에게 지급됩니다.
        """
        # 사용자_id가 "iiii"이면 명령어를 사용한 사람
        if user_id.lower() == "iiii":
            target_user = ctx.author
            target_user_id = ctx.author.id
        else:
            # 사용자_id를 정수로 변환 시도
            try:
                target_user_id = int(user_id)
            except ValueError:
                await ctx.send("❌ 사용자 ID는 숫자이거나 'iiii'여야 합니다.")
                return
            
            # 사용자 조회
            target_user = ctx.guild.get_member(target_user_id)
            if target_user is None:
                await ctx.send(f"❌ 사용자를 찾을 수 없습니다. (ID: {user_id})")
                return
        
        guild_id = ctx.guild.id
        
        # exp 지급
        result = await add_exp(target_user_id, guild_id, exp_amount)
        
        # 결과 메시지 생성
        embed = discord.Embed(
            title="레벨업 명령어 실행",
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
    
    @level_up_user.error
    async def level_up_user_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법: `!레벨업 [사용자_id] [exp수치]`\n예: `!레벨업 123456789 100` 또는 `!레벨업 iiii 100`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ exp 수치는 숫자여야 합니다.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

