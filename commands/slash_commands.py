# commands/slash_commands.py - Slash 명령어 (Beta V2)

"""
Beta V2: Prefix(!) 명령어를 Slash(/) 명령어로 전환
- /레벨, /순위, /마켓, /구매, /티켓목록 (일반 사용자)
- /jk [exp|level|points|market|study|...] (JK 관리자)
"""

import discord
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import psutil

from level_system import (
    add_exp, set_current_exp, add_level, set_level,
    add_points, set_points, calculate_required_exp, get_user_level_info
)
from database import (
    get_leaderboard_by_points, get_leaderboard_by_level,
    get_user_rank_by_points, get_user_rank_by_level,
    get_market_enabled, get_user, get_or_create_user,
    set_market_enabled,
    add_server_fee, remove_server_fee, get_server_fee_balance,
    get_all_users_for_nickname_refresh,
)
from market_manager import (
    get_all_market_items, find_item_by_code, purchase_ticket,
    get_user_purchase_history, ensure_market_dir, get_file_lock,
    parse_market_file, add_market_item, clear_market_file, remove_market_item, MarketItem,
)
from database import update_user_points
import os
from study_manager import (
    add_member_to_study, remove_member_from_study,
    add_warning_to_study_member, remove_warning_from_study_member,
    get_study_channel_id, get_study_member_warning, get_study_member_info,
    read_study_file, create_study, delete_study, get_study_file_path,
    list_all_studies,
)
from nickname_manager import update_user_nickname
from role_manager import update_tier_role, get_tier_for_level
from logger import send_command_log, send_levelup_log, send_tier_upgrade_log, send_warning_log, send_purchase_log
from warning_system import issue_warning, check_warning_restrictions, remove_warning
from voice_channel_exp_manager import load_voice_channel_exp, add_voice_channel_exp, remove_voice_channel_exp, update_voice_channel_exp
from level_ranges_manager import load_level_ranges, add_level_range, remove_level_ranges_by_range, update_level_range
from tier_roles_manager import load_tier_roles, add_tier_role, remove_tier_role
from config import VOICE_CHANNEL_EXP
from config import (
    RANK_COMMAND_CHANNEL_ID, MARKET_COMMAND_CHANNEL_ID,
    VOICE_CHANNEL_EXP, SERVER_FEE_LOG_CHANNEL_ID,
)
from utils import has_jk_role


def _check_jk(interaction: discord.Interaction) -> bool:
    return has_jk_role(interaction.user)


async def setup_slash_commands(bot: discord.Client):
    """Slash 명령어 등록"""

    # ========== 일반 명령어: /레벨, /순위, /마켓, /구매, /티켓목록 ==========

    @bot.tree.command(name="레벨", description="내 레벨 또는 다른 사용자의 레벨·경험치·포인트를 조회합니다")
    @app_commands.describe(member="레벨을 조회할 사용자 (비워두면 본인)")
    async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
        user_has_jk = _check_jk(interaction)
        if not user_has_jk and RANK_COMMAND_CHANNEL_ID and interaction.channel_id != RANK_COMMAND_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ 이 명령어는 <#{RANK_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        target = member or interaction.user
        level_info = await get_user_level_info(target.id, interaction.guild.id)
        restrictions = await check_warning_restrictions(target.id, interaction.guild.id)
        exp_progress = level_info['exp']
        exp_required = level_info['required_exp']
        progress_pct = (exp_progress / exp_required * 100) if exp_required > 0 else 100
        bar_len = 20
        filled = int(bar_len * (exp_progress / exp_required)) if exp_required > 0 else bar_len
        bar = "█" * filled + "░" * (bar_len - filled)
        tier_info = get_tier_for_level(level_info['level'])
        tier_name = tier_info[0] if tier_info else None
        tier_colors = {"브론즈": 0x8B4513, "실버": 0xC0C0C0, "골드": 0xFFD700, "플레티넘": 0x00FF00, "다이아": 0x00BFFF, "루비": 0xFF1493}
        color = discord.Color(tier_colors.get(tier_name, 0x3498db)) if tier_name in tier_colors else discord.Color.blue()

        embed = discord.Embed(title=f"{target.display_name}님의 레벨 정보", color=color)
        if restrictions['warning_count'] > 0:
            embed.add_field(name="⚠️ 경고", value=f"**{restrictions['warning_count']}회**", inline=False)
        if tier_name:
            embed.add_field(name="티어", value=f"**{tier_name}**", inline=False)
        embed.add_field(name="레벨", value=f"**{level_info['level']}**", inline=False)
        embed.add_field(name="경험치 진행률", value=f"{exp_progress:,} / {exp_required:,} ({progress_pct:.1f}%)\n`{bar}`", inline=False)
        embed.add_field(name="포인트", value=f"**{level_info['points']:,}**", inline=False)
        embed.add_field(name="총 경험치", value=f"**{level_info['total_exp']:,}**", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"다음 레벨까지 {exp_required - exp_progress:,} exp 남았습니다!")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="순위", description="서버 포인트/레벨 랭킹을 조회합니다")
    @app_commands.describe(sort_by="정렬 기준")
    @app_commands.choices(sort_by=[
        app_commands.Choice(name="포인트", value="포인트"),
        app_commands.Choice(name="레벨", value="레벨"),
    ])
    async def slash_rank(interaction: discord.Interaction, sort_by: app_commands.Choice[str] = None):
        user_has_jk = _check_jk(interaction)
        if not user_has_jk and RANK_COMMAND_CHANNEL_ID and interaction.channel_id != RANK_COMMAND_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ 이 명령어는 <#{RANK_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.",
                ephemeral=True
            )
            return

        sort_val = (sort_by.value if sort_by else "포인트")
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        if sort_val == "포인트":
            leaderboard = await get_leaderboard_by_points(guild_id, 10)
            user_rank = await get_user_rank_by_points(user_id, guild_id)
            sort_name = "포인트"
        else:
            leaderboard = await get_leaderboard_by_level(guild_id, 10)
            user_rank = await get_user_rank_by_level(user_id, guild_id)
            sort_name = "레벨"

        user_info = await get_user_level_info(user_id, guild_id)
        rank_text = ""
        medals = ["🥇", "🥈", "🥉"]
        for i, u in enumerate(leaderboard, 1):
            m = interaction.guild.get_member(u['user_id'])
            name = m.display_name if m else "알 수 없음"
            medal = medals[i - 1] if i <= 3 else f"{i}."
            val = u['points'] if sort_name == "포인트" else u['level']
            val_txt = f"{val:,} 포인트" if sort_name == "포인트" else f"레벨 {val}"
            rank_text += f"{medal} **{name}** - {val_txt}\n"

        uval = user_info['points'] if sort_name == "포인트" else user_info['level']
        uval_txt = f"{uval:,} 포인트" if sort_name == "포인트" else f"레벨 {uval}"

        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} {sort_name} 순위",
            description=rank_text or "순위 데이터가 없습니다.",
            color=discord.Color.gold()
        )
        embed.add_field(name="내 순위", value=f"**{user_rank}위** - {uval_txt}", inline=False)
        embed.set_footer(text=f"정렬 기준: {sort_name}")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="마켓", description="현재 판매 중인 마켓 물품 목록을 표시합니다")
    async def slash_market(interaction: discord.Interaction):
        user_has_jk = _check_jk(interaction)
        if not user_has_jk:
            r = await check_warning_restrictions(interaction.user.id, interaction.guild.id)
            if not r['can_use_market']:
                await interaction.response.send_message(
                    f"❌ 경고 5회 이상으로 마켓을 이용할 수 없습니다. (현재 경고: {r['warning_count']}회)",
                    ephemeral=True
                )
                return
            if not await get_market_enabled(interaction.guild.id):
                await interaction.response.send_message("❌ 현재 마켓이 비활성화되어 있습니다.", ephemeral=True)
                return
            if MARKET_COMMAND_CHANNEL_ID and interaction.channel_id != MARKET_COMMAND_CHANNEL_ID:
                await interaction.response.send_message(
                    f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return

        ensure_market_dir()
        all_items = get_all_market_items()
        items_flat = [item for items in all_items.values() for item in items]
        if not items_flat:
            await interaction.response.send_message("❌ 현재 판매 중인 물품이 없습니다.")
            return

        embed = discord.Embed(title="🛒 마켓", description="현재 판매 중인 물품 목록", color=discord.Color.green())
        for idx, item in enumerate(items_flat):
            tickets_sold = item.tickets_sold
            if item.is_role:
                fname = f"+ 역할 - {item.role_name}"
                fval = f"🎫 **{item.code}** (물품 코드)\n구매된 횟수 : {tickets_sold}"
            else:
                fname = f"**- {item.name}**"
                fval = (
                    f"🎫 **{item.code}** (물품 코드)\n\n"
                    f"**티켓 가격:** {item.price_per_ticket:,}포인트\n"
                    f"**뽑는 인원:** {item.draw_count}명\n"
                    f"**구매된 티켓 수:** {tickets_sold}티켓\n"
                    f"**1인당 최대:** {item.max_purchase}티켓"
                )
            if idx < len(items_flat) - 1:
                fval += "\n\n=========\n"
            embed.add_field(name=fname, value=fval, inline=False)
        embed.set_footer(text=f"총 {len(items_flat)}개의 물품 \n/구매 [물품코드]로 구매하세요!")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="구매", description="포인트로 마켓 물품을 구매합니다")
    @app_commands.describe(item_code="구매할 물품의 코드")
    async def slash_purchase(interaction: discord.Interaction, item_code: str):
        user_has_jk = _check_jk(interaction)
        if not user_has_jk:
            r = await check_warning_restrictions(interaction.user.id, interaction.guild.id)
            if not r['can_use_market']:
                await interaction.response.send_message(
                    f"❌ 경고 5회 이상으로 마켓을 이용할 수 없습니다.",
                    ephemeral=True
                )
                return
            if not await get_market_enabled(interaction.guild.id):
                await interaction.response.send_message("❌ 현재 마켓이 비활성화되어 있습니다.", ephemeral=True)
                return
            if MARKET_COMMAND_CHANNEL_ID and interaction.channel_id != MARKET_COMMAND_CHANNEL_ID:
                await interaction.response.send_message(
                    f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return

        result = find_item_by_code(item_code)
        if result is None:
            await interaction.response.send_message(f"❌ 물품 코드 `{item_code}`를 찾을 수 없습니다.", ephemeral=True)
            return
        filename, item = result

        if not item.is_available():
            await interaction.response.send_message(f"❌ `{item.name}`은(는) 품절되었습니다.", ephemeral=True)
            return

        user_id = interaction.user.id
        guild_id = interaction.guild.id
        user_name = interaction.user.display_name or str(interaction.user)
        user = await get_or_create_user(user_id, guild_id)
        user_points = int(user.get("points") or 0)

        if item.is_role:
            if not item.can_purchase(user_name):
                await interaction.response.send_message(f"❌ `{item.name}` 역할을 이미 보유하고 있습니다.", ephemeral=True)
                return
        else:
            uc = item.get_user_ticket_count(user_name)
            if uc >= item.max_purchase:
                await interaction.response.send_message(
                    f"❌ 한 사람당 최대 {item.max_purchase}개까지만 구매할 수 있습니다. (현재: {uc}개)",
                    ephemeral=True
                )
                return

        if user_points < item.price_per_ticket:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다. 필요: {item.price_per_ticket:,}, 보유: {user_points:,}",
                ephemeral=True
            )
            return

        member = None
        role = None
        if item.is_role:
            member = interaction.guild.get_member(user_id)
            if not member:
                await interaction.response.send_message("❌ 사용자를 찾을 수 없습니다.", ephemeral=True)
                return
            role = discord.utils.get(interaction.guild.roles, name=item.role_name)
            if not role:
                await interaction.response.send_message(f"❌ 역할 '{item.role_name}'을 찾을 수 없습니다.", ephemeral=True)
                return
            try:
                await member.add_roles(role, reason=f"마켓에서 {item.role_name} 역할 구매")
            except discord.Forbidden:
                await interaction.response.send_message("❌ 역할을 부여할 권한이 없습니다.", ephemeral=True)
                return

        new_points = user_points - item.price_per_ticket
        file_lock = await get_file_lock(filename)
        async with file_lock:
            await update_user_points(user_id, guild_id, new_points)
            success = purchase_ticket(filename, item.code, user_name)
        if not success:
            await update_user_points(user_id, guild_id, user_points)
            if item.is_role and member and role:
                try:
                    await member.remove_roles(role, reason="구매 처리 실패")
                except Exception:
                    pass
            await interaction.response.send_message("❌ 구매 처리 중 오류가 발생했습니다.", ephemeral=True)
            return

        embed = discord.Embed(title="✅ 구매 완료", color=discord.Color.green())
        if item.is_role:
            embed.description = f"**{item.role_name}** 역할을 구매했습니다!"
            embed.add_field(name="구매 정보", value=f"**물품 코드:** {item.code}\n**가격:** {item.price_per_ticket:,} 포인트\n**구매 후 포인트:** {new_points:,}", inline=False)
            await send_purchase_log(interaction.client, interaction.user, item.role_name, item.code, item.price_per_ticket, new_points, 1, 1)
        else:
            uc = item.get_user_ticket_count(user_name)
            embed.description = f"**{item.name}** 티켓을 구매했습니다!"
            embed.add_field(name="구매 정보", value=f"**물품 코드:** {item.code}\n**티켓 가격:** {item.price_per_ticket:,} 포인트\n**구매 후 포인트:** {new_points:,}\n**보유 티켓:** {uc}개 / {item.max_purchase}개", inline=False)
            await send_purchase_log(interaction.client, interaction.user, item.name, item.code, item.price_per_ticket, new_points, uc, item.max_purchase)
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="티켓목록", description="내가 구매한 티켓 목록을 조회합니다")
    async def slash_ticket_list(interaction: discord.Interaction):
        user_has_jk = _check_jk(interaction)
        if not user_has_jk:
            r = await check_warning_restrictions(interaction.user.id, interaction.guild.id)
            if not r['can_use_market']:
                await interaction.response.send_message(
                    f"❌ 경고 5회 이상으로 마켓을 이용할 수 없습니다.",
                    ephemeral=True
                )
                return
            if not await get_market_enabled(interaction.guild.id):
                await interaction.response.send_message("❌ 현재 마켓이 비활성화되어 있습니다.", ephemeral=True)
                return
            if MARKET_COMMAND_CHANNEL_ID and interaction.channel_id != MARKET_COMMAND_CHANNEL_ID:
                await interaction.response.send_message(
                    f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.",
                    ephemeral=True
                )
                return

        user_name = interaction.user.display_name
        user_purchases = get_user_purchase_history(user_name)
        if not user_purchases:
            embed = discord.Embed(title="🎫 티켓 목록", description="구매한 티켓이 없습니다.", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)
            return

        item_summary = {}
        for filename, item, ticket_count in user_purchases:
            if item.code not in item_summary:
                item_summary[item.code] = {
                    'name': item.name,
                    'total_count': 0,
                    'max_purchase': item.max_purchase,
                    'price': item.price_per_ticket,
                    'is_role': item.is_role,
                    'role_name': item.role_name if item.is_role else None
                }
            item_summary[item.code]['total_count'] += ticket_count

        embed = discord.Embed(
            title="🎫 티켓 목록",
            description=f"**{interaction.user.display_name}**님이 구매한 티켓 목록",
            color=discord.Color.blue()
        )
        for code, info in item_summary.items():
            total = info['total_count']
            if info['is_role']:
                embed.add_field(name=f"🎭 {code}", value=f"**역할:** {info['role_name']}\n**가격:** {info['price']:,} 포인트\n**상태:** 보유 중", inline=False)
            else:
                embed.add_field(name=f"🎫 {code}", value=f"**물품명:** {info['name']}\n**티켓 가격:** {info['price']:,} 포인트\n**보유 티켓:** {total}개 / {info['max_purchase']}개", inline=False)
        embed.set_footer(text=f"총 {len(item_summary)}개의 물품을 구매하셨습니다.")
        await interaction.response.send_message(embed=embed)

    # ========== /jk 그룹 (JK 관리자 전용) ==========

    jk_group = app_commands.Group(name="jk", description="JK 관리자 전용 명령어")

    exp_group = app_commands.Group(name="exp", description="경험치 관리", parent=jk_group)

    @exp_group.command(name="add", description="경험치 추가")
    @app_commands.describe(user="대상 사용자", amount="추가할 EXP 수치")
    async def jk_exp_add(interaction: discord.Interaction, user: discord.Member, amount: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        result = await add_exp(user.id, interaction.guild.id, amount)
        embed = discord.Embed(title="경험치 추가", color=discord.Color.green())
        embed.add_field(name="대상", value=user.display_name, inline=False)
        embed.add_field(name="추가된 EXP", value=f"+{amount:,}", inline=True)
        embed.add_field(name="현재 레벨", value=str(result['new_level']), inline=True)
        await interaction.response.send_message(embed=embed)
        if result['leveled_up']:
            await update_user_nickname(user, result['new_level'])
            await update_tier_role(user, result['new_level'])

    @exp_group.command(name="set", description="현재 레벨의 경험치 진행률 설정")
    @app_commands.describe(user="대상 사용자", amount="설정할 EXP 수치 (0 이상)")
    async def jk_exp_set(interaction: discord.Interaction, user: discord.Member, amount: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if amount < 0:
            await interaction.response.send_message("❌ 경험치는 0 이상이어야 합니다.", ephemeral=True)
            return
        result = await set_current_exp(user.id, interaction.guild.id, amount)
        progress_pct = (result['new_exp'] / result['required_exp'] * 100) if result['required_exp'] > 0 else 100
        embed = discord.Embed(title="경험치 설정", color=discord.Color.blue())
        embed.add_field(name="대상", value=user.display_name, inline=False)
        embed.add_field(name="새 EXP", value=f"**{result['new_exp']:,}** / {result['required_exp']:,} ({progress_pct:.1f}%)", inline=True)
        if result['old_level'] != result['new_level']:
            embed.add_field(name="레벨 변화", value=f"**{result['old_level']}** → **{result['new_level']}**", inline=True)
        await interaction.response.send_message(embed=embed)
        await update_user_nickname(user, result['new_level'])
        if result['old_level'] != result['new_level']:
            await update_tier_role(user, result['new_level'])

    level_group = app_commands.Group(name="level", description="레벨 관리", parent=jk_group)

    @level_group.command(name="add", description="레벨 추가")
    @app_commands.describe(user="대상 사용자", levels="추가할 레벨 수")
    async def jk_level_add(interaction: discord.Interaction, user: discord.Member, levels: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        result = await add_level(user.id, interaction.guild.id, levels)
        embed = discord.Embed(title="레벨 추가", color=discord.Color.green())
        embed.add_field(name="대상", value=user.display_name, inline=False)
        embed.add_field(name="추가된 레벨", value=f"+{levels}", inline=True)
        embed.add_field(name="이전/새 레벨", value=f"**{result['old_level']}** → **{result['new_level']}**", inline=True)
        await interaction.response.send_message(embed=embed)
        await update_user_nickname(user, result['new_level'])
        await update_tier_role(user, result['new_level'])

    @level_group.command(name="set", description="레벨 직접 설정")
    @app_commands.describe(user="대상 사용자", target_level="목표 레벨", award_points="레벨 상승 시 포인트 지급 여부")
    async def jk_level_set(interaction: discord.Interaction, user: discord.Member, target_level: int, award_points: bool = False):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if target_level < 1:
            await interaction.response.send_message("❌ 레벨은 1 이상이어야 합니다.", ephemeral=True)
            return
        result = await set_level(user.id, interaction.guild.id, target_level, award_points=award_points)
        embed = discord.Embed(title="레벨 설정", color=discord.Color.blue())
        embed.add_field(name="대상", value=user.display_name, inline=False)
        embed.add_field(name="이전/새 레벨", value=f"**{result['old_level']}** → **{result['new_level']}**", inline=True)
        if result.get('points_earned', 0) != 0:
            embed.add_field(name="포인트", value=f"+{result['points_earned']} (총 {result['new_points']:,})", inline=True)
        await interaction.response.send_message(embed=embed)
        await update_user_nickname(user, result['new_level'])
        await update_tier_role(user, result['new_level'])

    points_group = app_commands.Group(name="points", description="포인트 관리", parent=jk_group)

    @points_group.command(name="add", description="포인트 추가")
    @app_commands.describe(user="대상 사용자", amount="추가할 포인트")
    async def jk_points_add(interaction: discord.Interaction, user: discord.Member, amount: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        result = await add_points(user.id, interaction.guild.id, amount)
        embed = discord.Embed(title="포인트 추가", color=discord.Color.green())
        embed.add_field(name="대상", value=user.display_name, inline=False)
        embed.add_field(name="추가/새 포인트", value=f"+{amount:,} → **{result['new_points']:,}**", inline=True)
        await interaction.response.send_message(embed=embed)

    @points_group.command(name="set", description="포인트 직접 설정")
    @app_commands.describe(user="대상 사용자", amount="설정할 포인트 (0 이상)")
    async def jk_points_set(interaction: discord.Interaction, user: discord.Member, amount: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if amount < 0:
            await interaction.response.send_message("❌ 포인트는 0 이상이어야 합니다.", ephemeral=True)
            return
        result = await set_points(user.id, interaction.guild.id, amount)
        embed = discord.Embed(title="포인트 설정", color=discord.Color.blue())
        embed.add_field(name="대상", value=user.display_name, inline=False)
        embed.add_field(name="이전/새 포인트", value=f"**{result['old_points']:,}** → **{result['new_points']:,}**", inline=True)
        await interaction.response.send_message(embed=embed)

    @jk_group.command(name="warning", description="경고 부여")
    @app_commands.describe(member="대상 사용자", count="경고 수 (1~10)", reason="사유")
    async def jk_warning(interaction: discord.Interaction, member: discord.Member, count: int = 1, reason: str = "사유 없음"):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if count < 1 or count > 10:
            await interaction.response.send_message("❌ 경고 수는 1~10이어야 합니다.", ephemeral=True)
            return
        result = await issue_warning(member.id, interaction.guild.id, reason.strip() or "사유 없음", interaction.user.id, count)
        restrictions = await check_warning_restrictions(member.id, interaction.guild.id)
        embed = discord.Embed(title="⚠️ 경고 부여 완료", color=discord.Color.orange())
        embed.add_field(name="대상", value=member.display_name, inline=False)
        embed.add_field(name="부여/총 경고", value=f"**{result['warning_count']}개** / 총 **{result['total_warnings']}개**", inline=True)
        embed.add_field(name="포인트 차감", value=f"-{result['points_deducted']:,} (잔액 {result['new_points']:,})", inline=True)
        embed.add_field(name="사유", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_warning_log(interaction.client, interaction.user, member, result['warning_count'], reason, result['total_warnings'], result['points_deducted'], result['new_points'])
        if restrictions['should_ban']:
            try:
                await member.timeout(timedelta(hours=24), reason=f"경고 {result['total_warnings']}회 누적")
                await interaction.followup.send(f"⚠️ {member.mention}님은 경고 10회 이상으로 24시간 임시 차단되었습니다.")
            except discord.Forbidden:
                await interaction.followup.send("❌ 사용자를 차단할 권한이 없습니다.")

    @jk_group.command(name="unwarn", description="경고 해제")
    @app_commands.describe(member="대상 사용자", count="해제할 경고 수")
    async def jk_unwarn(interaction: discord.Interaction, member: discord.Member, count: int = 1):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if count < 1:
            await interaction.response.send_message("❌ 해제할 경고 수는 1 이상이어야 합니다.", ephemeral=True)
            return
        result = await remove_warning(member.id, interaction.guild.id, count)
        if result['removed_count'] == 0:
            await interaction.response.send_message(f"❌ {member.display_name}님에게 해제할 경고가 없습니다.", ephemeral=True)
            return
        embed = discord.Embed(title="✅ 경고 해제", color=discord.Color.green())
        embed.add_field(name="대상", value=member.display_name, inline=False)
        embed.add_field(name="해제/남은 경고", value=f"**{result['removed_count']}개** 해제, 남은 경고 **{result['total_warnings']}개**", inline=True)
        await interaction.response.send_message(embed=embed)

    server_fee_group = app_commands.Group(name="server_fee", description="서버비 관리", parent=jk_group)

    @server_fee_group.command(name="add", description="서버비 추가 기록")
    @app_commands.describe(member="기여자 (선택)", amount="금액", reason="사유")
    async def jk_server_fee_add(interaction: discord.Interaction, amount: int, reason: str = "사유 없음", member: discord.Member = None):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ 금액은 0보다 커야 합니다.", ephemeral=True)
            return
        user_id = member.id if member else None
        await add_server_fee(user_id, interaction.guild.id, amount, reason.strip() or "사유 없음", interaction.user.id)
        balance = await get_server_fee_balance(interaction.guild.id)
        embed = discord.Embed(title="✅ 서버비 추가 완료", color=discord.Color.green())
        embed.add_field(name="기여자", value=member.display_name if member else "익명", inline=False)
        embed.add_field(name="추가/잔액", value=f"+{amount:,}원 / 잔액 **{balance:,}원**", inline=True)
        await interaction.response.send_message(embed=embed)
        if SERVER_FEE_LOG_CHANNEL_ID:
            try:
                log_ch = interaction.client.get_channel(SERVER_FEE_LOG_CHANNEL_ID)
                if log_ch:
                    await log_ch.send(embed=discord.Embed(title="💰 서버비 추가", description=f"기여: {member.display_name if member else '익명'}\n+{amount:,}원\n잔액: {balance:,}원", color=discord.Color.green()))
            except Exception:
                pass

    @server_fee_group.command(name="remove", description="서버비 사용 기록")
    @app_commands.describe(amount="사용 금액", reason="사유")
    async def jk_server_fee_remove(interaction: discord.Interaction, amount: int, reason: str = "사유 없음"):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ 금액은 0보다 커야 합니다.", ephemeral=True)
            return
        await remove_server_fee(interaction.guild.id, amount, reason.strip() or "사유 없음", interaction.user.id)
        balance = await get_server_fee_balance(interaction.guild.id)
        embed = discord.Embed(title="✅ 서버비 사용 기록", color=discord.Color.blue())
        embed.add_field(name="사용/잔액", value=f"-{amount:,}원 / 잔액 **{balance:,}원**", inline=True)
        await interaction.response.send_message(embed=embed)

    market_group = app_commands.Group(name="market", description="마켓 관리", parent=jk_group)

    @market_group.command(name="toggle", description="마켓 사용 가능 여부 전환")
    async def jk_market_toggle(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        current = await get_market_enabled(interaction.guild.id)
        await set_market_enabled(interaction.guild.id, not current)
        status = "활성화" if not current else "비활성화"
        await interaction.response.send_message(f"✅ 마켓이 **{status}**되었습니다.")

    @market_group.command(name="list", description="마켓 파일(market.txt) 내용 조회")
    async def jk_market_list(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        ensure_market_dir()
        items = parse_market_file("market.txt")
        if not items:
            await interaction.response.send_message("❌ 마켓에 등록된 물품이 없습니다.")
            return
        lines = []
        for i, item in enumerate(items, 1):
            t = "역할" if item.is_role else "티켓"
            lines.append(f"{i}. [{t}] {item.code} - {item.name} (가격: {item.price_per_ticket:,}P)")
        embed = discord.Embed(title="📋 마켓 목록 (market.txt)", description="\n".join(lines), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    @market_group.command(name="clear", description="마켓 파일 전체 삭제 (확인 후 실행)")
    async def jk_market_clear(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        file_lock = await get_file_lock("market.txt")
        async with file_lock:
            ok = clear_market_file("market.txt")
        if not ok:
            await interaction.response.send_message("❌ market.txt 파일을 찾을 수 없습니다.")
            return
        await interaction.response.send_message("✅ 마켓(market.txt) 내용이 모두 삭제되었습니다.")

    @market_group.command(name="remove", description="마켓에서 물품 코드로 제거")
    @app_commands.describe(code="물품 코드")
    async def jk_market_remove(interaction: discord.Interaction, code: str):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        file_lock = await get_file_lock("market.txt")
        async with file_lock:
            ok = remove_market_item("market.txt", code)
        if not ok:
            await interaction.response.send_message(f"❌ 물품 코드 `{code}`를 찾을 수 없습니다.")
            return
        await interaction.response.send_message(f"✅ 마켓에서 `{code}`가 제거되었습니다.")

    @market_group.command(name="add_ticket", description="티켓 물품 추가")
    @app_commands.describe(name="물품 이름", code="물품 코드", draw_count="뽑는 인원 수", max_purchase="1인당 최대 구매", price="티켓 가격(포인트)")
    async def jk_market_add_ticket(interaction: discord.Interaction, name: str, code: str, draw_count: int, max_purchase: int, price: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if draw_count < 1 or max_purchase < 1 or price < 0:
            await interaction.response.send_message("❌ 뽑는 인원·1인당 구매·가격은 1 이상이어야 합니다.", ephemeral=True)
            return
        file_lock = await get_file_lock("market.txt")
        async with file_lock:
            item = MarketItem(name=name, code=code, draw_count=draw_count, max_purchase=max_purchase, price_per_ticket=price, quantity=0, tickets_sold=0, buyers=[], is_role=False, role_name=None)
            ok = add_market_item("market.txt", item)
        if not ok:
            await interaction.response.send_message(f"❌ 물품 코드 `{code}`가 이미 존재합니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ 티켓 물품 **{name}** (`{code}`) 추가 완료. 가격 {price:,}P")

    @market_group.command(name="add_role", description="역할 판매 추가")
    @app_commands.describe(role_name="역할 이름", code="물품 코드", price="가격(포인트)")
    async def jk_market_add_role(interaction: discord.Interaction, role_name: str, code: str, price: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if price < 0:
            await interaction.response.send_message("❌ 가격은 0 이상이어야 합니다.", ephemeral=True)
            return
        file_lock = await get_file_lock("market.txt")
        async with file_lock:
            item = MarketItem(name=f"역할: {role_name}", code=code, draw_count=1, max_purchase=1, price_per_ticket=price, quantity=0, tickets_sold=0, buyers=[], is_role=True, role_name=role_name)
            ok = add_market_item("market.txt", item)
        if not ok:
            await interaction.response.send_message(f"❌ 물품 코드 `{code}`가 이미 존재합니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ 역할 **{role_name}** (`{code}`) 추가 완료. 가격 {price:,}P")

    study_group = app_commands.Group(name="study", description="스터디 관리", parent=jk_group)

    @study_group.command(name="add", description="스터디에 멤버 추가")
    @app_commands.describe(study_name="스터디 이름", member="추가할 멤버", memo="메모 (선택)")
    async def jk_study_add(interaction: discord.Interaction, study_name: str, member: discord.Member, memo: str = ""):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        success = add_member_to_study(study_name, member.id, memo.strip())
        if not success:
            await interaction.response.send_message(f"❌ {member.display_name}님은 이미 `{study_name}` 스터디에 있거나, 스터디가 없습니다.", ephemeral=True)
            return
        study_channel_id = get_study_channel_id(study_name)
        if study_channel_id and interaction.guild:
            role = discord.utils.get(interaction.guild.roles, name=study_name)
            if role and member not in role.members:
                await member.add_roles(role, reason=f"스터디 '{study_name}' 멤버 추가")
        await interaction.response.send_message(f"✅ {member.display_name}님을 **{study_name}** 스터디에 추가했습니다.")

    @study_group.command(name="remove", description="스터디에서 멤버 제거")
    @app_commands.describe(study_name="스터디 이름", member="제거할 멤버")
    async def jk_study_remove(interaction: discord.Interaction, study_name: str, member: discord.Member):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        success = remove_member_from_study(study_name, member.id)
        if not success:
            await interaction.response.send_message(f"❌ {member.display_name}님은 `{study_name}` 스터디에 없습니다.", ephemeral=True)
            return
        role = discord.utils.get(interaction.guild.roles, name=study_name)
        if role and member in role.members:
            await member.remove_roles(role, reason=f"스터디 '{study_name}' 멤버 제거")
        await interaction.response.send_message(f"✅ {member.display_name}님을 **{study_name}** 스터디에서 제거했습니다.")

    @study_group.command(name="log", description="스터디 목록 (이름, 대표방, 역할, 참여 인원)")
    async def jk_study_log(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        study_names = list_all_studies()
        if not study_names:
            await interaction.response.send_message("❌ 등록된 스터디가 없습니다.")
            return
        embed = discord.Embed(title="📋 스터디 목록", color=discord.Color.blue())
        guild = interaction.guild
        for name in sorted(study_names):
            channel_id, members = read_study_file(name)
            # 대표방: 회의실 채널
            rep_room = "—"
            if channel_id and guild:
                ch = guild.get_channel(channel_id)
                rep_room = ch.mention if ch else f"ID: {channel_id}"
            # 역할: 스터디 이름과 같은 이름의 역할
            role = discord.utils.get(guild.roles, name=name) if guild else None
            role_str = role.mention if role else "—"
            # 참여 인원
            member_mentions = []
            for uid in list(members.keys())[:15]:
                member_mentions.append(f"<@{uid}>")
            if len(members) > 15:
                member_mentions.append(f"외 {len(members) - 15}명")
            members_str = ", ".join(member_mentions) if member_mentions else "없음"
            value = (
                f"**대표방:** {rep_room}\n"
                f"**역할:** {role_str}\n"
                f"**참여 인원 ({len(members)}명):** {members_str}"
            )
            embed.add_field(name=name, value=value, inline=False)
        embed.set_footer(text=f"총 {len(study_names)}개 스터디")
        await interaction.response.send_message(embed=embed)

    @study_group.command(name="warnlog", description="스터디 멤버 경고/정보 조회")
    @app_commands.describe(study_name="스터디 이름", member="멤버 (비워두면 전체)")
    async def jk_study_warn_log(interaction: discord.Interaction, study_name: str, member: discord.Member = None):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if not os.path.exists(get_study_file_path(study_name)):
            await interaction.response.send_message(f"❌ `{study_name}` 스터디를 찾을 수 없습니다.", ephemeral=True)
            return
        channel_id, members = read_study_file(study_name)
        if member:
            info = get_study_member_info(study_name, member.id)
            if not info:
                await interaction.response.send_message(f"❌ {member.display_name}님은 `{study_name}` 스터디에 없습니다.", ephemeral=True)
                return
            warn_count, memo = info
            embed = discord.Embed(title=f"📋 {study_name} 멤버 정보", color=discord.Color.blue())
            embed.add_field(name="멤버", value=member.display_name, inline=False)
            embed.add_field(name="경고", value=str(warn_count), inline=True)
            embed.add_field(name="메모", value=memo or "-", inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            if not members:
                await interaction.response.send_message(f"❌ `{study_name}` 스터디에 멤버가 없습니다.", ephemeral=True)
                return
            lines = []
            for uid, (warn_count, memo) in members.items():
                lines.append(f"<@{uid}> 경고 {warn_count}회 | {memo or '-'}")
            embed = discord.Embed(title=f"📋 {study_name} 전체 멤버", description="\n".join(lines[:25]), color=discord.Color.blue())
            if len(lines) > 25:
                embed.set_footer(text=f"외 {len(lines)-25}명")
            await interaction.response.send_message(embed=embed)

    @study_group.command(name="create", description="스터디 생성 및 회의실 ID 설정")
    @app_commands.describe(study_name="스터디 이름", channel_id="회의실(음성채널) ID")
    async def jk_study_create(interaction: discord.Interaction, study_name: str, channel_id: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if create_study(study_name, channel_id):
            await interaction.response.send_message(f"✅ 스터디 **{study_name}** 생성 완료. 회의실 ID: {channel_id}")
        else:
            await interaction.response.send_message(f"❌ `{study_name}` 스터디가 이미 있거나 생성 실패.", ephemeral=True)

    @study_group.command(name="delete", description="스터디 삭제")
    @app_commands.describe(study_name="스터디 이름")
    async def jk_study_delete(interaction: discord.Interaction, study_name: str):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if not os.path.exists(get_study_file_path(study_name)):
            await interaction.response.send_message(f"❌ `{study_name}` 스터디를 찾을 수 없습니다.", ephemeral=True)
            return
        _, members = read_study_file(study_name)
        count = len(members)
        ok = delete_study(study_name)
        if not ok:
            await interaction.response.send_message("❌ 삭제 실패.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ 스터디 **{study_name}** 삭제 완료. (멤버 {count}명)")

    @study_group.command(name="warn", description="스터디 멤버에게 경고 부여")
    @app_commands.describe(study_name="스터디 이름", member="대상 멤버", reason="사유")
    async def jk_study_warn(interaction: discord.Interaction, study_name: str, member: discord.Member, reason: str = "사유 없음"):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        ok = add_warning_to_study_member(study_name, member.id, reason.strip() or "사유 없음")
        if not ok:
            await interaction.response.send_message(f"❌ {member.display_name}님은 `{study_name}` 스터디에 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ **{study_name}** 스터디 {member.display_name}님에게 경고 부여: {reason}")

    @study_group.command(name="unwarn", description="스터디 멤버 경고 제거")
    @app_commands.describe(study_name="스터디 이름", member="대상 멤버")
    async def jk_study_unwarn(interaction: discord.Interaction, study_name: str, member: discord.Member):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        ok = remove_warning_from_study_member(study_name, member.id)
        if not ok:
            await interaction.response.send_message(f"❌ {member.display_name}님은 `{study_name}` 스터디에 없거나 경고가 0입니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ **{study_name}** 스터디 {member.display_name}님 경고 1회 제거.")

    voice_group = app_commands.Group(name="voice", description="음성채널 EXP 설정", parent=jk_group)

    @voice_group.command(name="list", description="음성채널 EXP 설정 목록")
    async def jk_voice_list(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        settings = load_voice_channel_exp()
        if not settings:
            settings = VOICE_CHANNEL_EXP or {}
        if not settings:
            await interaction.response.send_message("❌ 등록된 음성채널 EXP 설정이 없습니다.")
            return
        lines = []
        for cid, (n, m) in sorted(settings.items()):
            ch = interaction.guild.get_channel(cid) if interaction.guild else None
            name = ch.name if ch else str(cid)
            lines.append(f"• {name}: {n}분마다 {m} exp")
        embed = discord.Embed(title="📋 음성채널 EXP 설정", description="\n".join(lines), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    @voice_group.command(name="add", description="음성채널 EXP 설정 추가")
    @app_commands.describe(channel_id="음성채널 ID", interval_minutes="지급 주기(분)", exp_amount="지급 경험치")
    async def jk_voice_add(interaction: discord.Interaction, channel_id: int, interval_minutes: int, exp_amount: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if interval_minutes < 1 or exp_amount < 1:
            await interaction.response.send_message("❌ 주기와 경험치는 1 이상이어야 합니다.", ephemeral=True)
            return
        add_voice_channel_exp(channel_id, interval_minutes, exp_amount)
        await interaction.response.send_message(f"✅ 채널 ID `{channel_id}`: {interval_minutes}분마다 {exp_amount} exp 추가.")

    @voice_group.command(name="remove", description="음성채널 EXP 설정 제거")
    @app_commands.describe(channel_id="음성채널 ID")
    async def jk_voice_remove(interaction: discord.Interaction, channel_id: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        remove_voice_channel_exp(channel_id)
        await interaction.response.send_message(f"✅ 채널 ID `{channel_id}` EXP 설정 제거됨.")

    level_system_group = app_commands.Group(name="level_system", description="레벨 구간 설정", parent=jk_group)

    @level_system_group.command(name="list", description="레벨 구간 설정 목록")
    async def jk_level_system_list(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        ranges = load_level_ranges()
        if not ranges:
            await interaction.response.send_message("❌ 등록된 레벨 구간이 없습니다.")
            return
        sorted_ranges = sorted(ranges.items(), key=lambda x: x[0][0])
        lines = [f"{s}~{e}레벨: {minu}분, {pts}포인트" for (s, e), (minu, pts) in sorted_ranges]
        embed = discord.Embed(title="📋 레벨 구간 설정", description="\n".join(lines), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    @level_system_group.command(name="set", description="레벨 구간 설정 추가/수정")
    @app_commands.describe(start="시작 레벨", end="끝 레벨", minutes="레벨업 시간(분)", points="레벨업 포인트")
    async def jk_level_system_set(interaction: discord.Interaction, start: int, end: int, minutes: int, points: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if start < 1 or end < start or minutes < 1 or points < 0:
            await interaction.response.send_message("❌ 시작≤끝 레벨, 분·포인트는 1 이상.", ephemeral=True)
            return
        if (start, end) in load_level_ranges():
            update_level_range(start, end, minutes, points)
            await interaction.response.send_message(f"✅ {start}~{end}레벨 구간 수정: {minutes}분, {points}P")
        else:
            add_level_range(start, end, minutes, points)
            await interaction.response.send_message(f"✅ {start}~{end}레벨 구간 추가: {minutes}분, {points}P")

    @level_system_group.command(name="remove", description="레벨 구간 제거")
    @app_commands.describe(start="시작 레벨", end="끝 레벨")
    async def jk_level_system_remove(interaction: discord.Interaction, start: int, end: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        removed = remove_level_ranges_by_range(start, end)
        if not removed:
            await interaction.response.send_message(f"❌ {start}~{end} 구간을 찾을 수 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ {start}~{end} 레벨 구간 제거됨.")

    tier_system_group = app_commands.Group(name="tier_system", description="티어 역할 설정", parent=jk_group)

    @tier_system_group.command(name="list", description="티어 역할 목록")
    async def jk_tier_system_list(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        roles = load_tier_roles()
        if not roles:
            await interaction.response.send_message("❌ 등록된 티어 역할이 없습니다.")
            return
        sorted_roles = sorted(roles.items(), key=lambda x: x[1][0], reverse=True)
        lines = [f"{name}: 레벨 {lv} 이상 → {rname}" for name, (lv, rname) in sorted_roles]
        embed = discord.Embed(title="📋 티어 역할 설정", description="\n".join(lines), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    @tier_system_group.command(name="set", description="티어 역할 설정 추가/수정")
    @app_commands.describe(tier_name="티어 이름", required_level="필요 레벨", role_name="역할 이름")
    async def jk_tier_system_set(interaction: discord.Interaction, tier_name: str, required_level: int, role_name: str):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if required_level < 0:
            await interaction.response.send_message("❌ 레벨은 0 이상이어야 합니다.", ephemeral=True)
            return
        add_tier_role(tier_name, required_level, role_name)
        await interaction.response.send_message(f"✅ 티어 **{tier_name}**: 레벨 {required_level} 이상 → **{role_name}**")

    @tier_system_group.command(name="remove", description="티어 제거")
    @app_commands.describe(tier_name="티어 이름")
    async def jk_tier_system_remove(interaction: discord.Interaction, tier_name: str):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        ok = remove_tier_role(tier_name)
        if not ok:
            await interaction.response.send_message(f"❌ 티어 `{tier_name}`를 찾을 수 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ 티어 **{tier_name}** 제거됨.")

    @jk_group.command(name="message", description="위 메시지를 지정 채널로 복사")
    @app_commands.describe(channel="도착 채널")
    async def jk_message(interaction: discord.Interaction, channel: discord.TextChannel):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        hist = [m async for m in interaction.channel.history(limit=2)]
        if len(hist) < 2:
            await interaction.followup.send("❌ 복사할 메시지가 없습니다.", ephemeral=True)
            return
        target_msg = hist[1]
        files = []
        for att in target_msg.attachments:
            files.append(await att.to_file())
        try:
            if target_msg.embeds:
                for emb in target_msg.embeds:
                    await channel.send(content=target_msg.content, embed=emb, files=files if files else None)
            else:
                if target_msg.content or files:
                    await channel.send(content=target_msg.content, files=files if files else None)
                else:
                    await interaction.followup.send("❌ 복사할 내용이 없습니다.", ephemeral=True)
                    return
        except discord.Forbidden:
            await interaction.followup.send("❌ 해당 채널에 보낼 권한이 없습니다.", ephemeral=True)
            return
        await interaction.followup.send(f"✅ {interaction.channel.mention} → {channel.mention} 로 메시지 복사 완료.", ephemeral=True)

    @jk_group.command(name="clear", description="메시지 삭제")
    @app_commands.describe(count="삭제할 메시지 수 (1~500)")
    async def jk_clear(interaction: discord.Interaction, count: int):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        if count < 1 or count > 500:
            await interaction.response.send_message("❌ 1~500 사이로 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = 0
        remaining = count
        is_first = True
        while remaining > 0:
            limit = min(remaining, 100) + (1 if is_first else 0)
            purged = await interaction.channel.purge(limit=limit)
            if not purged:
                break
            if is_first:
                deleted += len(purged) - 1
                is_first = False
            else:
                deleted += len(purged)
            remaining -= len(purged)
            if remaining > 0:
                await asyncio.sleep(0.5)
        await interaction.followup.send(f"✅ {deleted}개 메시지 삭제됨.", ephemeral=True)

    @jk_group.command(name="reboot", description="티어 시스템 재설정 (닉네임·역할 동기화)")
    async def jk_reboot(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        await interaction.response.send_message("🔄 티어 시스템 재설정 중...")
        users = await get_all_users_for_nickname_refresh()
        updated = 0
        for u in users:
            guild = interaction.guild if u['guild_id'] == interaction.guild.id else interaction.client.get_guild(u['guild_id'])
            if not guild:
                continue
            member = guild.get_member(u['user_id'])
            if not member:
                continue
            success, old_t, new_t = await update_tier_role(member, u['level'])
            if success and old_t != new_t:
                updated += 1
            await asyncio.sleep(0.05)
        await interaction.followup.send(f"✅ 완료. {len(users)}명 중 {updated}명 티어 변경됨.")

    debug_group = app_commands.Group(name="debug", description="디버그/상태 조회", parent=jk_group)

    @debug_group.command(name="system", description="시스템 리소스 (CPU, RAM)")
    async def jk_debug_system(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        embed = discord.Embed(title="💻 시스템 리소스", color=discord.Color.blue())
        embed.add_field(name="CPU", value=f"{cpu:.1f}%", inline=True)
        embed.add_field(name="RAM", value=f"{mem.used / (1024**3):.2f} GB / {mem.total / (1024**3):.2f} GB", inline=True)
        await interaction.response.send_message(embed=embed)

    @debug_group.command(name="exp", description="현재 시간대 경험치 획득 가능 여부")
    async def jk_debug_exp(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        now = datetime.now()
        can_earn = 6 <= now.hour < 24
        embed = discord.Embed(
            title="🔍 경험치 획득 시간 체크",
            color=discord.Color.green() if can_earn else discord.Color.red(),
        )
        embed.add_field(name="현재 시간", value=f"{now.hour:02d}:{now.minute:02d}", inline=True)
        embed.add_field(name="상태", value="✅ 획득 가능" if can_earn else "❌ 획득 불가", inline=True)
        embed.add_field(name="경험치 획득 가능 시간", value="06:00 ~ 23:59", inline=False)
        await interaction.response.send_message(embed=embed)

    @debug_group.command(name="participants", description="음성채널 EXP 참여자 현황")
    async def jk_debug_participants(interaction: discord.Interaction):
        if not _check_jk(interaction):
            await interaction.response.send_message("❌ JK 역할이 필요합니다.", ephemeral=True)
            return
        voice_exp = load_voice_channel_exp()
        if not voice_exp:
            voice_exp = VOICE_CHANNEL_EXP or {}
        if not voice_exp:
            await interaction.response.send_message("❌ EXP 지급 채널이 설정되지 않았습니다.")
            return
        if not hasattr(interaction.client, 'voice_monitor') or interaction.client.voice_monitor is None:
            await interaction.response.send_message("❌ Voice monitor가 초기화되지 않았습니다.")
            return
        await interaction.response.defer()
        voice_monitor = interaction.client.voice_monitor
        await voice_monitor.ensure_sessions_for_guild(interaction.guild)
        active_sessions = voice_monitor.active_sessions
        embed = discord.Embed(title="🔍 음성채널 참여자 현황", color=discord.Color.blue())
        has_any = False
        for channel_id, (interval_min, exp_amt) in voice_exp.items():
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                continue
            members = [m for m in channel.members if not m.bot]
            if not members:
                continue
            has_any = True
            lines = []
            for member in members:
                sess = active_sessions.get(member.id)
                if sess and sess.get('channel_id') == channel_id:
                    join_t = sess['join_time']
                    dur = datetime.now() - join_t
                    dur_m = int(dur.total_seconds() / 60)
                    # 이번 세션에서 받은 exp (06~24시만)
                    earned = 0
                    t = join_t + timedelta(minutes=interval_min)
                    while t <= datetime.now():
                        if 6 <= t.hour < 24:
                            earned += exp_amt
                        t += timedelta(minutes=interval_min)
                    lines.append(f"{member.display_name}: {dur_m}분 / {earned}exp")
                else:
                    lines.append(f"{member.display_name}: 0분 / 0exp")
            embed.add_field(
                name=f"🎤 {channel.name} ({len(members)}명)",
                value="\n".join(lines) + f"\n(설정: {interval_min}분마다 {exp_amt} EXP)",
                inline=False,
            )
        if not has_any:
            embed.add_field(name="정보", value="현재 EXP 지급 채널에 참여자가 없습니다.", inline=False)
        await interaction.followup.send(embed=embed)

    bot.tree.add_command(jk_group)
