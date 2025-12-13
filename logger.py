# logger.py - 로그 시스템

import discord
from datetime import datetime
from config import LOG_CHANNEL_ID


async def send_command_log(bot, executor: discord.Member, command: str, target_user: discord.Member = None, details: str = ""):
    """
    !jk 명령어 실행 로그 전송
    """
    if LOG_CHANNEL_ID is None:
        return
    
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            print(f"[Logger] 로그 채널을 찾을 수 없습니다. (ID: {LOG_CHANNEL_ID})")
            return
        
        embed = discord.Embed(
            title="📝 JK 명령어 실행 로그",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="실행자",
            value=f"{executor.display_name} ({executor.mention})\nID: {executor.id}",
            inline=False
        )
        
        embed.add_field(
            name="명령어",
            value=f"`{command}`",
            inline=False
        )
        
        if target_user:
            embed.add_field(
                name="대상 사용자",
                value=f"{target_user.display_name} ({target_user.mention})\nID: {target_user.id}",
                inline=False
            )
        
        if details:
            embed.add_field(
                name="상세 정보",
                value=details,
                inline=False
            )
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Logger] 로그 전송 실패: {e}")


async def send_levelup_log(bot, user: discord.Member, old_level: int, new_level: int, points_earned: int, new_points: int, source: str = "음성채널"):
    """
    레벨업 로그 전송
    """
    if LOG_CHANNEL_ID is None:
        return
    
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            print(f"[Logger] 로그 채널을 찾을 수 없습니다. (ID: {LOG_CHANNEL_ID})")
            return
        
        embed = discord.Embed(
            title="🎉 레벨업 로그",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="사용자",
            value=f"{user.display_name} ({user.mention})\nID: {user.id}",
            inline=False
        )
        
        embed.add_field(
            name="레벨 변화",
            value=f"**{old_level}** → **{new_level}**",
            inline=True
        )
        
        embed.add_field(
            name="획득 포인트",
            value=f"**+{points_earned:,}**",
            inline=True
        )
        
        embed.add_field(
            name="현재 포인트",
            value=f"**{new_points:,}**",
            inline=True
        )
        
        embed.add_field(
            name="발생 경로",
            value=source,
            inline=False
        )
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Logger] 레벨업 로그 전송 실패: {e}")

