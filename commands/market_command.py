# commands/market_command.py - !마켓, !구매 명령어

import discord
from discord.ext import commands
from database import get_user, get_or_create_user, update_user_points
from market_manager import (
    get_all_market_items, find_item_by_code, purchase_ticket,
    ensure_market_dir, get_user_purchase_history
)
from logger import send_purchase_log
from warning_system import check_warning_restrictions
from config import MARKET_COMMAND_CHANNEL_ID
from database import get_market_enabled
from utils import has_jk_role


def market_command(k):

    @k.command(name="마켓")
    async def show_market(ctx):
        """
        마켓의 모든 물품 정보를 표시합니다.
        사용법: !마켓
        """
        user_has_jk = has_jk_role(ctx.author)
        if not user_has_jk:
            restrictions = await check_warning_restrictions(ctx.author.id, ctx.guild.id)
            if not restrictions['can_use_market']:
                await ctx.send(f"❌ 경고 5회 이상으로 마켓을 이용할 수 없습니다. (현재 경고: {restrictions['warning_count']}회)")
                return
        if not user_has_jk:
            market_enabled = await get_market_enabled(ctx.guild.id)
            if not market_enabled:
                await ctx.send("❌ 현재 마켓이 비활성화되어 있습니다. 관리자에게 문의하세요.")
                return
        if not user_has_jk and MARKET_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != MARKET_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return

        ensure_market_dir()
        all_items = get_all_market_items()

        if not all_items:
            await ctx.send("❌ 현재 판매 중인 물품이 없습니다.")
            return

        embed = discord.Embed(
            title="🛒 마켓",
            description="현재 판매 중인 물품 목록",
            color=discord.Color.green()
        )
        total_items = sum(len(items) for items in all_items.values())
        item_count = 0
        for filename, items in all_items.items():
            for item in items:
                item_count += 1
                if item.is_role:
                    field_name = f"+ 역할 - {item.role_name}"
                    field_value = (
                        f"🎫 **{item.code}** (물품 코드)\n"
                        f"구매된 횟수 : {item.tickets_sold}"
                    )
                else:
                    field_name = f"**- {item.name}**"
                    field_value = (
                        f"🎫 **{item.code}** (물품 코드)\n\n"
                        f"**티켓 가격:** {item.price_per_ticket:,}포인트\n"
                        f"**뽑는 인원:** {item.draw_count}명\n"
                        f"**구매된 티켓 수:** {item.tickets_sold}티켓\n"
                        f"**1인당 최대:** {item.max_purchase}티켓"
                    )
                if item_count < total_items:
                    field_value += "\n\n=========\n"
                embed.add_field(name=field_name, value=field_value, inline=False)

        if item_count == 0:
            await ctx.send("❌ 현재 판매 중인 물품이 없습니다.")
            return
        embed.set_footer(text=f"총 {item_count}개의 물품 \n!구매 [물품코드]로 구매하세요!")
        await ctx.send(embed=embed)

    @k.command(name="구매")
    async def purchase_item(ctx, item_code: str = None):
        """티켓을 구매합니다. 사용법: !구매 [물품 코드]"""
        user_has_jk = has_jk_role(ctx.author)
        if not user_has_jk:
            restrictions = await check_warning_restrictions(ctx.author.id, ctx.guild.id)
            if not restrictions['can_use_market']:
                await ctx.send(f"❌ 경고 5회 이상으로 마켓을 이용할 수 없습니다. (현재 경고: {restrictions['warning_count']}회)")
                return
        if not user_has_jk:
            market_enabled = await get_market_enabled(ctx.guild.id)
            if not market_enabled:
                await ctx.send("❌ 현재 마켓이 비활성화되어 있습니다. 관리자에게 문의하세요.")
                return
        if not user_has_jk and MARKET_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != MARKET_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return

        if item_code is None:
            await ctx.send("❌ 사용법: `!구매 [물품코드]`\n예: `!구매 ABC123`")
            return

        ensure_market_dir()
        result = find_item_by_code(item_code)
        if result is None:
            await ctx.send(f"❌ 물품 코드 `{item_code}`를 찾을 수 없습니다. `!마켓`으로 확인해주세요.")
            return

        filename, item = result
        if not item.is_available():
            await ctx.send(f"❌ `{item.name}`은(는) 품절되었습니다.")
            return

        user_id = ctx.author.id
        guild_id = ctx.guild.id
        user = await get_or_create_user(user_id, guild_id)
        user_name = ctx.author.display_name or str(ctx.author)
        try:
            user_points = int(user.get("points") or 0)
        except (TypeError, ValueError):
            user_points = 0

        if item.is_role:
            if not item.can_purchase(user_name):
                await ctx.send(f"❌ `{item.name}` 역할을 이미 보유하고 있습니다.")
                return
        else:
            user_ticket_count = item.get_user_ticket_count(user_name)
            if not item.can_purchase(user_name):
                await ctx.send(
                    f"❌ `{item.name}`은(는) 한 사람당 최대 {item.max_purchase}개까지만 구매할 수 있습니다.\n"
                    f"현재 구매한 티켓: {user_ticket_count}개"
                )
                return

        if user_points < item.price_per_ticket:
            await ctx.send(
                f"❌ 포인트가 부족합니다.\n"
                f"필요한 포인트: {item.price_per_ticket:,}\n"
                f"보유 포인트: {user_points:,}"
            )
            return

        user_ticket_count = item.get_user_ticket_count(user_name) if not item.is_role else 0

        if item.is_role:
            embed = discord.Embed(
                title="🛒 역할 구매 확인",
                description=f"**{item.role_name}** 역할을 구매하시겠습니까?",
                color=discord.Color.blue()
            )
            embed.add_field(name="물품 정보", value=(
                f"**역할 이름:** {item.role_name}\n"
                f"**물품 코드:** {item.code}\n"
                f"**가격:** {item.price_per_ticket:,} 포인트"
            ), inline=False)
            embed.add_field(name="구매 정보", value=(
                f"**보유 포인트:** {user_points:,}\n"
                f"**구매 후 포인트:** {user_points - item.price_per_ticket:,}"
            ), inline=False)
        else:
            embed = discord.Embed(
                title="🛒 티켓 구매 확인",
                description=f"**{item.name}** 티켓을 구매하시겠습니까?",
                color=discord.Color.blue()
            )
            embed.add_field(name="물품 정보", value=(
                f"**물품명:** {item.name}\n"
                f"**물품 코드:** {item.code}\n"
                f"**티켓 가격:** {item.price_per_ticket:,} 포인트"
            ), inline=False)
            embed.add_field(name="구매 정보", value=(
                f"**보유 포인트:** {user_points:,}\n"
                f"**구매 후 포인트:** {user_points - item.price_per_ticket:,}\n"
                f"**현재 구매한 티켓:** {user_ticket_count}개 / {item.max_purchase}개"
            ), inline=False)

        embed.set_footer(text="구매를 확인하려면 아래 버튼을 눌러주세요.")
        view = PurchaseConfirmView(
            item=item,
            filename=filename,
            user_id=user_id,
            guild_id=guild_id,
            user_name=user_name,
            price=item.price_per_ticket,
            user_points=user_points
        )
        await ctx.send(embed=embed, view=view)

    @k.command(name="티켓목록")
    async def show_ticket_list(ctx):
        """자신이 구매한 티켓 목록을 표시합니다."""
        user_has_jk = has_jk_role(ctx.author)
        if not user_has_jk:
            restrictions = await check_warning_restrictions(ctx.author.id, ctx.guild.id)
            if not restrictions['can_use_market']:
                await ctx.send(f"❌ 경고 5회 이상으로 마켓을 이용할 수 없습니다. (현재 경고: {restrictions['warning_count']}회)")
                return
        if not user_has_jk:
            market_enabled = await get_market_enabled(ctx.guild.id)
            if not market_enabled:
                await ctx.send("❌ 현재 마켓이 비활성화되어 있습니다. 관리자에게 문의하세요.")
                return
        if not user_has_jk and MARKET_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != MARKET_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return

        ensure_market_dir()
        user_name = ctx.author.display_name
        user_purchases = get_user_purchase_history(user_name)

        if not user_purchases:
            embed = discord.Embed(
                title="🎫 티켓 목록",
                description="구매한 티켓이 없습니다.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🎫 티켓 목록",
            description=f"**{user_name}**님이 구매한 티켓 목록",
            color=discord.Color.blue()
        )
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

        for item_code, info in item_summary.items():
            if info['is_role']:
                field_value = (
                    f"**역할 이름:** {info['role_name']}\n"
                    f"**가격:** {info['price']:,} 포인트\n"
                    f"**상태:** 보유 중"
                )
                embed.add_field(name=f"🎭 {item_code}", value=field_value, inline=False)
            else:
                field_value = (
                    f"**물품명:** {info['name']}\n"
                    f"**티켓 가격:** {info['price']:,} 포인트\n"
                    f"**보유 티켓:** {info['total_count']}개 / {info['max_purchase']}개"
                )
                embed.add_field(name=f"🎫 {item_code}", value=field_value, inline=False)

        embed.set_footer(text=f"총 {len(item_summary)}개의 물품을 구매하셨습니다.")
        await ctx.send(embed=embed)


class PurchaseConfirmView(discord.ui.View):
    """구매 확인 버튼 뷰"""

    def __init__(self, item, filename: str, user_id: int, guild_id: int,
                 user_name: str, price: int, user_points: int):
        super().__init__(timeout=60)
        self.item = item
        self.filename = filename
        self.user_id = user_id
        self.guild_id = guild_id
        self.user_name = user_name
        self.price = price
        self.user_points = user_points
        self.purchased = False

    @discord.ui.button(label="✅ 구매 확인", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 구매할 수 있습니다.", ephemeral=True)
            return

        user = await get_user(self.user_id, self.guild_id)
        if user is None:
            await interaction.response.send_message("❌ 사용자 정보를 찾을 수 없습니다.", ephemeral=True)
            return
        try:
            current_points = int(user.get('points') or 0)
        except (TypeError, ValueError):
            current_points = 0
        if current_points < self.price:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다.\n필요: {self.price:,}, 보유: {current_points:,}",
                ephemeral=True
            )
            return

        from market_manager import get_file_lock, purchase_ticket, find_item_by_code
        file_lock = await get_file_lock(self.filename)

        async with file_lock:
            result = find_item_by_code(self.item.code)
            if result is None:
                await interaction.response.send_message("❌ 물품을 찾을 수 없습니다.", ephemeral=True)
                return
            _, updated_item = result

            if updated_item.is_role:
                if not updated_item.can_purchase(self.user_name):
                    await interaction.response.send_message(
                        f"❌ 이미 {updated_item.role_name} 역할을 보유하고 있습니다.",
                        ephemeral=True
                    )
                    return
            else:
                user_ticket_count = updated_item.get_user_ticket_count(self.user_name)
                if not updated_item.can_purchase(self.user_name):
                    await interaction.response.send_message(
                        f"❌ 최대 구매 가능 수를 초과했습니다.\n현재: {user_ticket_count}개 / 최대: {updated_item.max_purchase}개",
                        ephemeral=True
                    )
                    return

            if not updated_item.is_available():
                await interaction.response.send_message("❌ 품절되었습니다.", ephemeral=True)
                return

            new_points = current_points - self.price
            await update_user_points(self.user_id, self.guild_id, new_points)

            if updated_item.is_role:
                guild = interaction.guild
                member = guild.get_member(self.user_id)
                if member is None:
                    await update_user_points(self.user_id, self.guild_id, current_points)
                    await interaction.response.send_message("❌ 사용자를 찾을 수 없습니다.", ephemeral=True)
                    return
                role = discord.utils.get(guild.roles, name=updated_item.role_name)
                if role is None:
                    await update_user_points(self.user_id, self.guild_id, current_points)
                    await interaction.response.send_message(f"❌ 역할 '{updated_item.role_name}'을(를) 찾을 수 없습니다.", ephemeral=True)
                    return
                try:
                    await member.add_roles(role, reason=f"마켓에서 {updated_item.role_name} 역할 구매")
                except discord.Forbidden:
                    await update_user_points(self.user_id, self.guild_id, current_points)
                    await interaction.response.send_message("❌ 역할을 부여할 권한이 없습니다.", ephemeral=True)
                    return
                except Exception as e:
                    await update_user_points(self.user_id, self.guild_id, current_points)
                    await interaction.response.send_message(f"❌ 역할 부여 중 오류가 발생했습니다: {e}", ephemeral=True)
                    return

                success = purchase_ticket(self.filename, self.item.code, self.user_name)
                if not success:
                    await update_user_points(self.user_id, self.guild_id, current_points)
                    try:
                        await member.remove_roles(role, reason="구매 처리 실패로 인한 역할 제거")
                    except Exception:
                        pass
                    await interaction.response.send_message("❌ 구매 처리 중 오류가 발생했습니다.", ephemeral=True)
                    return

                self.purchased = True
                success_embed = discord.Embed(
                    title="✅ 구매 완료",
                    description=f"**{updated_item.role_name}** 역할을 구매했습니다!",
                    color=discord.Color.green()
                )
                success_embed.add_field(name="구매 정보", value=(
                    f"**물품 코드:** {self.item.code}\n"
                    f"**역할 이름:** {updated_item.role_name}\n"
                    f"**가격:** {self.price:,} 포인트\n"
                    f"**구매 후 포인트:** {new_points:,}"
                ), inline=False)
                await interaction.response.edit_message(embed=success_embed, view=None)
                await send_purchase_log(
                    interaction.client, interaction.user,
                    updated_item.role_name, self.item.code, self.price, new_points, 1, 1
                )
            else:
                success = purchase_ticket(self.filename, self.item.code, self.user_name)
                if not success:
                    await update_user_points(self.user_id, self.guild_id, current_points)
                    await interaction.response.send_message("❌ 구매 처리 중 오류가 발생했습니다.", ephemeral=True)
                    return
                self.purchased = True
                user_ticket_count = updated_item.get_user_ticket_count(self.user_name)
                success_embed = discord.Embed(
                    title="✅ 구매 완료",
                    description=f"**{updated_item.name}** 티켓을 구매했습니다!",
                    color=discord.Color.green()
                )
                success_embed.add_field(name="구매 정보", value=(
                    f"**물품 코드:** {self.item.code}\n"
                    f"**티켓 가격:** {self.price:,} 포인트\n"
                    f"**구매 후 포인트:** {new_points:,}\n"
                    f"**보유 티켓:** {user_ticket_count + 1}개 / {updated_item.max_purchase}개"
                ), inline=False)
                await interaction.response.edit_message(embed=success_embed, view=None)
                await send_purchase_log(
                    interaction.client, interaction.user,
                    self.item.name, self.item.code, self.price, new_points,
                    user_ticket_count + 1, updated_item.max_purchase
                )

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 취소할 수 있습니다.", ephemeral=True)
            return
        cancel_embed = discord.Embed(title="❌ 구매 취소", description="구매가 취소되었습니다.", color=discord.Color.red())
        await interaction.response.edit_message(embed=cancel_embed, view=None)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
