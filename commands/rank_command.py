# commands/rank_command.py - !순위 명령어

import discord
from discord.ext import commands
from database import (
    get_leaderboard_by_points, get_leaderboard_by_level,
    get_user_rank_by_points, get_user_rank_by_level
)
from level_system import get_user_level_info
from config import RANK_COMMAND_CHANNEL_ID
from utils import has_jk_role


def rank_command(k):

    @k.command(name="순위")
    async def show_rank(ctx, sort_by: str = "포인트"):
        """
        순위를 표시합니다.
        사용법: !순위 [포인트|레벨]
        기본값: 포인트
        """
        # JK 권한 체크 (JK 권한이 있으면 채널 제한 무시)
        user_has_jk = has_jk_role(ctx.author)
        
        # 채널 제한 체크 (JK 권한이 없을 때만)
        if not user_has_jk and RANK_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != RANK_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{RANK_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return
        
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        
        # 정렬 기준 확인
        if sort_by.lower() in ["포인트", "point", "points", "p"]:
            leaderboard = await get_leaderboard_by_points(guild_id, limit=10)
            user_rank = await get_user_rank_by_points(user_id, guild_id)
            sort_name = "포인트"
        elif sort_by.lower() in ["레벨", "level", "levels", "l"]:
            leaderboard = await get_leaderboard_by_level(guild_id, limit=10)
            user_rank = await get_user_rank_by_level(user_id, guild_id)
            sort_name = "레벨"
        else:
            await ctx.send("❌ 정렬 기준을 올바르게 입력해주세요. (`포인트` 또는 `레벨`)")
            return
        
        # 사용자 정보 조회
        user_info = await get_user_level_info(user_id, guild_id)
        
        # 순위 문자열 생성
        rank_text = ""
        medals = ["🥇", "🥈", "🥉"]
        
        for i, user_data in enumerate(leaderboard, 1):
            member = ctx.guild.get_member(user_data['user_id'])
            if member is None:
                name = "알 수 없음"
            else:
                name = member.display_name
            
            medal = medals[i - 1] if i <= 3 else f"{i}."
            
            if sort_name == "포인트":
                value = user_data['points']
                value_text = f"{value:,} 포인트"
            else:
                value = user_data['level']
                value_text = f"레벨 {value}"
            
            rank_text += f"{medal} **{name}** - {value_text}\n"
        
        # 사용자 자신의 정보
        if sort_name == "포인트":
            user_value = user_info['points']
            user_value_text = f"{user_value:,} 포인트"
        else:
            user_value = user_info['level']
            user_value_text = f"레벨 {user_value}"
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"📊 {ctx.guild.name} {sort_name} 순위",
            description=rank_text or "순위 데이터가 없습니다.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="내 순위",
            value=f"**{user_rank}위** - {user_value_text}",
            inline=False
        )
        
        embed.set_footer(text=f"정렬 기준: {sort_name} | !순위 포인트 또는 !순위 레벨")
        
        await ctx.send(embed=embed)

