# commands/market_command.py - !마켓, !구매 명령어

import discord
from discord.ext import commands
from database import get_user, update_user_points
from market_manager import (
    get_all_market_items, find_item_by_code, purchase_ticket,
    ensure_market_dir, get_user_purchase_history
)
from logger import send_purchase_log
from config import MARKET_COMMAND_CHANNEL_ID


def market_command(k):

    @k.command(name="마켓")
    async def show_market(ctx):
        """
        마켓의 모든 물품 정보를 표시합니다.
        사용법: !마켓
        """
        # 채널 제한 체크
        if MARKET_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != MARKET_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return
        
        ensure_market_dir()
        
        all_items = get_all_market_items()
        
        if not all_items:
            await ctx.send("❌ 현재 판매 중인 물품이 없습니다.")
            return
        
        # 임베드 생성
        embed = discord.Embed(
            title="🛒 마켓",
            description="현재 판매 중인 물품 목록",
            color=discord.Color.green()
        )
        
        # 전체 아이템 수 계산
        total_items = sum(len(items) for items in all_items.values())
        
        item_count = 0
        for filename, items in all_items.items():
            for item in items:
                item_count += 1
                
                # 필드 값 생성
                field_value = (
                    f"🎫 **{item.code}** (물품 코드)\n\n"
                    f"**티켓 가격:** {item.price_per_ticket:,}포인트\n"
                    f"**뽑는 인원:** {item.draw_count}명\n"
                    f"**구매된 티켓 수:** {item.tickets_sold}티켓\n"
                    f"**1인당 최대:** {item.max_purchase}티켓"
                )
                
                # 마지막 물품이 아니면 간격 추가 (세 줄)
                if item_count < total_items:
                    field_value += "\n\n=========\n"
                
                embed.add_field(
                    name=f"**- {item.name}**",
                    value=field_value,
                    inline=False
                )
        
        if item_count == 0:
            await ctx.send("❌ 현재 판매 중인 물품이 없습니다.")
            return
        
        embed.set_footer(text=f"총 {item_count}개의 물품 \n!구매 [물품코드]로 구매하세요!")
        
        await ctx.send(embed=embed)
    
    @k.command(name="구매")
    async def purchase_item(ctx, item_code: str = None):
        """
        티켓을 구매합니다.
        사용법: !구매 [물품 코드]
        """
        # 채널 제한 체크
        if MARKET_COMMAND_CHANNEL_ID is not None:
            if ctx.channel.id != MARKET_COMMAND_CHANNEL_ID:
                await ctx.send(f"❌ 이 명령어는 <#{MARKET_COMMAND_CHANNEL_ID}> 채널에서만 사용할 수 있습니다.")
                return
        
        if item_code is None:
            await ctx.send("❌ 사용법: `!구매 [물품코드]`\n예: `!구매 ABC123`")
            return
        
        ensure_market_dir()
        
        # 아이템 찾기
        result = find_item_by_code(item_code)
        if result is None:
            await ctx.send(f"❌ 물품 코드 `{item_code}`를 찾을 수 없습니다. `!마켓`으로 확인해주세요.")
            return
        
        filename, item = result
        
        # 구매 가능 여부 확인
        if not item.is_available():
            await ctx.send(f"❌ `{item.name}`은(는) 품절되었습니다.")
            return
        
        # 사용자 정보 조회
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        user = await get_user(user_id, guild_id)
        
        if user is None:
            await ctx.send("❌ 사용자 정보를 찾을 수 없습니다.")
            return
        
        user_name = ctx.author.display_name
        user_points = user['points']
        
        # 구매 가능 수 확인
        user_ticket_count = item.get_user_ticket_count(user_name)
        if not item.can_purchase(user_name):
            await ctx.send(
                f"❌ `{item.name}`은(는) 한 사람당 최대 {item.max_purchase}개까지만 구매할 수 있습니다.\n"
                f"현재 구매한 티켓: {user_ticket_count}개"
            )
            return
        
        # 포인트 확인
        if user_points < item.price_per_ticket:
            await ctx.send(
                f"❌ 포인트가 부족합니다.\n"
                f"필요한 포인트: {item.price_per_ticket:,}\n"
                f"보유 포인트: {user_points:,}"
            )
            return
        
        # 확인 버튼 생성
        embed = discord.Embed(
            title="🛒 티켓 구매 확인",
            description=f"**{item.name}** 티켓을 구매하시겠습니까?",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="물품 정보",
            value=(
                f"**물품명:** {item.name}\n"
                f"**물품 코드:** {item.code}\n"
                f"**티켓 가격:** {item.price_per_ticket:,} 포인트"
            ),
            inline=False
        )
        
        embed.add_field(
            name="구매 정보",
            value=(
                f"**보유 포인트:** {user_points:,}\n"
                f"**구매 후 포인트:** {user_points - item.price_per_ticket:,}\n"
                f"**현재 구매한 티켓:** {user_ticket_count}개 / {item.max_purchase}개"
            ),
            inline=False
        )
        
        embed.set_footer(text="구매를 확인하려면 아래 버튼을 눌러주세요.")
        
        # 버튼 생성
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
        """
        자신이 구매한 티켓 목록을 표시합니다.
        사용법: !티켓목록
        """
        # 채널 제한 체크
        if MARKET_COMMAND_CHANNEL_ID is not None:
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
        
        # 임베드 생성
        embed = discord.Embed(
            title="🎫 티켓 목록",
            description=f"**{user_name}**님이 구매한 티켓 목록",
            color=discord.Color.blue()
        )
        
        # 물품별로 그룹화 (같은 물품이 여러 파일에 있을 수 있음)
        item_summary = {}  # {item_code: (item_name, total_count, max_purchase)}
        
        for filename, item, ticket_count in user_purchases:
            if item.code not in item_summary:
                item_summary[item.code] = {
                    'name': item.name,
                    'total_count': 0,
                    'max_purchase': item.max_purchase,
                    'price': item.price_per_ticket
                }
            item_summary[item.code]['total_count'] += ticket_count
        
        # 필드 추가
        for item_code, info in item_summary.items():
            field_value = (
                f"**물품명:** {info['name']}\n"
                f"**티켓 가격:** {info['price']:,} 포인트\n"
                f"**보유 티켓:** {info['total_count']}개 / {info['max_purchase']}개"
            )
            
            embed.add_field(
                name=f"🎫 {item_code}",
                value=field_value,
                inline=False
            )
        
        embed.set_footer(text=f"총 {len(item_summary)}개의 물품을 구매하셨습니다.")
        
        await ctx.send(embed=embed)


class PurchaseConfirmView(discord.ui.View):
    """구매 확인 버튼 뷰"""
    
    def __init__(self, item, filename: str, user_id: int, guild_id: int, 
                 user_name: str, price: int, user_points: int):
        super().__init__(timeout=60)  # 60초 타임아웃
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
        
        # 다시 한번 확인 (포인트, 구매 가능 수)
        user = await get_user(self.user_id, self.guild_id)
        if user is None:
            await interaction.response.send_message("❌ 사용자 정보를 찾을 수 없습니다.", ephemeral=True)
            return
        
        current_points = user['points']
        if current_points < self.price:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다.\n필요: {self.price:,}, 보유: {current_points:,}",
                ephemeral=True
            )
            return
        
        # 아이템 정보 다시 확인
        from market_manager import find_item_by_code
        result = find_item_by_code(self.item.code)
        if result is None:
            await interaction.response.send_message("❌ 물품을 찾을 수 없습니다.", ephemeral=True)
            return
        
        _, updated_item = result
        
        # 구매 가능 수 확인
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
        
        # 포인트 차감
        new_points = current_points - self.price
        await update_user_points(self.user_id, self.guild_id, new_points)
        
        # 티켓 구매 처리
        success = purchase_ticket(self.filename, self.item.code, self.user_name)
        
        if not success:
            # 실패 시 포인트 복구
            await update_user_points(self.user_id, self.guild_id, current_points)
            await interaction.response.send_message("❌ 구매 처리 중 오류가 발생했습니다.", ephemeral=True)
            return
        
        self.purchased = True
        
        # 성공 메시지
        success_embed = discord.Embed(
            title="✅ 구매 완료",
            description=f"**{self.item.name}** 티켓을 구매했습니다!",
            color=discord.Color.green()
        )
        
        success_embed.add_field(
            name="구매 정보",
            value=(
                f"**물품 코드:** {self.item.code}\n"
                f"**티켓 가격:** {self.price:,} 포인트\n"
                f"**구매 후 포인트:** {new_points:,}\n"
                f"**보유 티켓:** {user_ticket_count + 1}개 / {updated_item.max_purchase}개"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=success_embed, view=None)
        
        # 로그 전송
        await send_purchase_log(
            interaction.client,
            interaction.user,
            self.item.name,
            self.item.code,
            self.price,
            new_points,
            user_ticket_count + 1,  # 구매 후 티켓 수
            updated_item.max_purchase
        )
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인만 취소할 수 있습니다.", ephemeral=True)
            return
        
        cancel_embed = discord.Embed(
            title="❌ 구매 취소",
            description="구매가 취소되었습니다.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
    
    async def on_timeout(self):
        # 타임아웃 시 버튼 비활성화
        for item in self.children:
            item.disabled = True

