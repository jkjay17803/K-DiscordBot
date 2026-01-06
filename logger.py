# logger.py - 로그 시스템

import discord
from datetime import datetime
from config import LOG_CHANNEL_ID_JK, LOG_CHANNEL_ID_LEVEL, LOG_CHANNEL_ID_MARKET, TIER_CONGRATULATION_CHANNEL_ID


async def send_command_log(bot, executor: discord.Member, command: str, target_user: discord.Member = None, details: str = ""):
    """
    !jk 명령어 실행 로그 전송
    """
    if LOG_CHANNEL_ID_JK is None:
        return
    
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID_JK)
        if channel is None:
            print(f"[Logger] JK 로그 채널을 찾을 수 없습니다. (ID: {LOG_CHANNEL_ID_JK})")
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
        else:
            # 사용자 ID만 있는 경우 (명령어 문자열에서 추출 시도)
            import re
            id_match = re.search(r'\d{17,19}', command)
            if id_match:
                user_id = id_match.group(0)
                embed.add_field(
                    name="대상 사용자",
                    value=f"ID: {user_id}",
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
    if LOG_CHANNEL_ID_LEVEL is None:
        return
    
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID_LEVEL)
        if channel is None:
            print(f"[Logger] LEVEL 로그 채널을 찾을 수 없습니다. (ID: {LOG_CHANNEL_ID_LEVEL})")
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
            value=f"**{old_level}** → **{new_level}**\n",
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


async def send_purchase_log(bot, user: discord.Member, item_name: str, item_code: str, price: int, remaining_points: int, user_ticket_count: int = 0, max_purchase: int = 0):
    """
    티켓 구매 로그 전송
    """
    if LOG_CHANNEL_ID_MARKET is None:
        return
    
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID_MARKET)
        if channel is None:
            print(f"[Logger] MARKET 로그 채널을 찾을 수 없습니다. (ID: {LOG_CHANNEL_ID_MARKET})")
            return
        
        embed = discord.Embed(
            title="🛒 티켓 구매 로그",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="구매자",
            value=f"{user.display_name} ({user.mention})\nID: {user.id}",
            inline=False
        )
        
        embed.add_field(
            name="물품 정보",
            value=f"**{item_name}**\n코드: `{item_code}`",
            inline=False
        )
        
        embed.add_field(
            name="구매 가격",
            value=f"**{price:,}** 포인트",
            inline=True
        )
        
        embed.add_field(
            name="구매 후 포인트",
            value=f"**{remaining_points:,}** 포인트",
            inline=True
        )
        
        if max_purchase > 0:
            embed.add_field(
                name="보유 티켓",
                value=f"**{user_ticket_count}/{max_purchase}**",
                inline=False
            )
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Logger] 구매 로그 전송 실패: {e}")


async def send_tier_upgrade_log(bot, user: discord.Member, old_tier: str, new_tier: str, level: int):
    """
    티어 업그레이드 축하 메시지 전송
    """
    if TIER_CONGRATULATION_CHANNEL_ID is None:
        return
    
    try:
        channel = bot.get_channel(TIER_CONGRATULATION_CHANNEL_ID)
        if channel is None:
            print(f"[Logger] 티어 축하 채널을 찾을 수 없습니다. (ID: {TIER_CONGRATULATION_CHANNEL_ID})")
            return
        
        # 티어 이모지 매핑
        tier_emojis = {
            "브론즈": "🥉",
            "실버": "🥈",
            "골드": "🥇",
            "다이아": "💎",
            "플레티넘": "💠",
            "루비": "💍"
        }
        
        old_emoji = tier_emojis.get(old_tier, "🏅")
        new_emoji = tier_emojis.get(new_tier, "🏅")
        
        embed = discord.Embed(
            title=f"{new_emoji} 티어 업그레이드!",
            description=f"**{user.display_name}** ({user.mention})님이 **{new_tier}** 티어에 도달했습니다!",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="티어 변화",
            value=f"{old_emoji} **{old_tier}** → {new_emoji} **{new_tier}**",
            inline=False
        )
        
        embed.add_field(
            name="현재 레벨",
            value=f"**{level}**",
            inline=True
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="축하합니다! 🎉")
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Logger] 티어 업그레이드 축하 메시지 전송 실패: {e}")
