# commands/level_command.py - !레벨 명령어

import discord
from discord.ext import commands
from level_system import get_user_level_info
from config import RANK_COMMAND_CHANNEL_ID

# 명령어가 이미 등록되었는지 확인하는 플래그
_level_command_registered = False


def level_command(k):
    global _level_command_registered
    
    # 이미 등록되었다면 스킵
    if _level_command_registered:
        return
    
    

    @k.command(name="레벨")
    async def show_level(ctx, member: discord.Member = None):
        """
        사용자의 레벨, 포인트, exp 정보를 표시합니다.
        사용법: !레벨 [@사용자]
        멘션을 하지 않으면 자신의 레벨 정보를 표시합니다.
        """
        # 채널 제한 체크
        if RANK_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != RANK_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{RANK_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return
        
        # 멘션된 사용자가 있으면 해당 사용자, 없으면 명령어 사용자
        target_member = member if member is not None else ctx.author
        user_id = target_member.id
        guild_id = ctx.guild.id
        
        # 레벨 정보 조회
        level_info = await get_user_level_info(user_id, guild_id)
        
        # exp 진행률 계산
        exp_progress = level_info['exp']
        exp_required = level_info['required_exp']
        progress_percentage = (exp_progress / exp_required * 100) if exp_required > 0 else 100
        
        # 진행률 바 생성 (20칸)
        bar_length = 20
        filled = int(bar_length * (exp_progress / exp_required)) if exp_required > 0 else bar_length
        bar = "█" * filled + "░" * (bar_length - filled)
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"{target_member.display_name}의 레벨 정보",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="레벨",
            value=f"**{level_info['level']}**",
            inline=False
        )
        
        embed.add_field(
            name="경험치 진행률",
            value=f"{exp_progress:,} / {exp_required:,} ({progress_percentage:.1f}%)\n`{bar}`",
            inline=False
        )
        
        embed.add_field(
            name="포인트",
            value=f"**{level_info['points']:,}**",
            inline=False
        )
        
        embed.add_field(
            name="총 경험치",
            value=f"**{level_info['total_exp']:,}**",
            inline=False
        )
        
        embed.set_thumbnail(url=target_member.display_avatar.url)
        embed.set_footer(text=f"다음 레벨까지 {exp_required - exp_progress:,} exp 남았습니다!")
        
        await ctx.send(embed=embed)
    
    # 명령어 등록 완료 플래그 설정
    _level_command_registered = True
