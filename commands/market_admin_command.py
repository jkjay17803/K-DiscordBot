# commands/market_admin_command.py - JK 마켓 관리 명령어

import discord
from discord.ext import commands
from datetime import datetime
from market_manager import (
    parse_market_file, save_market_file, add_market_item, clear_market_file,
    remove_market_item, MarketItem, get_file_lock, ensure_market_dir
)
from utils import has_jk_role


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


class MarketClearConfirmView(discord.ui.View):
    """마켓 클리어 확인 버튼 뷰"""
    
    def __init__(self, filename: str):
        super().__init__(timeout=60)  # 60초 타임아웃
        self.filename = filename
        self.cleared = False
    
    @discord.ui.button(label="✅ 클리어 확인", style=discord.ButtonStyle.red)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.cleared:
            await interaction.response.send_message("❌ 이미 클리어되었습니다.", ephemeral=True)
            return
        
        # 파일 락 획득
        file_lock = await get_file_lock(self.filename)
        
        async with file_lock:
            # 마켓 파일 클리어
            success = clear_market_file(self.filename)
            
            if not success:
                await interaction.response.send_message(f"❌ `{self.filename}` 파일을 찾을 수 없습니다.", ephemeral=True)
                return
            
            self.cleared = True
            
            # 성공 메시지
            success_embed = discord.Embed(
                title="✅ 마켓 클리어 완료",
                description=f"**{self.filename}** 파일의 모든 내용이 삭제되었습니다.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            await interaction.response.edit_message(embed=success_embed, view=None)
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.grey)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cancel_embed = discord.Embed(
            title="❌ 클리어 취소",
            description="마켓 클리어가 취소되었습니다.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
    
    async def on_timeout(self):
        # 타임아웃 시 버튼 비활성화
        for item in self.children:
            item.disabled = True


def market_admin_command(k):

    # ========== !jk마켓 명령어 그룹 ==========
    @k.group(name="jk마켓")
    @check_jk()
    async def jk_market_group(ctx):
        """JK 마켓 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk마켓 리스트` 또는 `!jk마켓 클리어` 또는 `!jk마켓 add`")

    @jk_market_group.command(name="리스트")
    @check_jk()
    async def market_list_command(ctx):
        """마켓 파일 내용 조회"""
        ensure_market_dir()
        
        try:
            items = parse_market_file("market.txt")
            
            if not items:
                await ctx.send("❌ 마켓에 등록된 물품이 없습니다.")
                return
            
            embed = discord.Embed(
                title="📋 마켓 물품 목록",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for idx, item in enumerate(items, 1):
                if item.is_role:
                    field_value = (
                        f"**코드:** {item.code}\n"
                        f"**역할 이름:** {item.role_name}\n"
                        f"**가격:** {item.price_per_ticket:,} 포인트\n"
                        f"**구매된 횟수:** {item.tickets_sold}회"
                    )
                    field_name = f"🎭 {idx}. {item.name}"
                else:
                    field_value = (
                        f"**코드:** {item.code}\n"
                        f"**뽑는 인원:** {item.draw_count}명\n"
                        f"**1인당 최대 구매:** {item.max_purchase}개\n"
                        f"**티켓 가격:** {item.price_per_ticket:,} 포인트\n"
                        f"**구매된 티켓 수:** {item.tickets_sold}개"
                    )
                    field_name = f"🎫 {idx}. {item.name}"
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text=f"총 {len(items)}개의 물품")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_market_group.command(name="클리어")
    @check_jk()
    async def market_clear_command(ctx):
        """마켓 파일 내용 모두 비우기 (확인 절차 필요)"""
        ensure_market_dir()
        
        try:
            # 현재 물품 수 확인
            items = parse_market_file("market.txt")
            item_count = len(items)
            
            # 확인 임베드 생성
            embed = discord.Embed(
                title="⚠️ 마켓 클리어 확인",
                description="**market.txt** 파일의 모든 내용을 정말 삭제하시겠습니까?",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="현재 상태",
                value=f"**등록된 물품:** {item_count}개",
                inline=False
            )
            embed.add_field(
                name="⚠️ 경고",
                value="이 작업은 되돌릴 수 없습니다. 모든 물품 정보와 구매 기록이 삭제됩니다.",
                inline=False
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            
            # 확인 버튼 생성
            view = MarketClearConfirmView("market.txt")
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_market_group.command(name="제거")
    @check_jk()
    async def market_remove_command(ctx, item_code: str = None):
        """마켓에서 물품 제거"""
        if item_code is None:
            await ctx.send("❌ 사용법: `!jk마켓 제거 [물품_코드]`\n예: `!jk마켓 제거 ABC12345`")
            return
        
        ensure_market_dir()
        
        try:
            # 파일 락 획득
            file_lock = await get_file_lock("market.txt")
            
            async with file_lock:
                # 아이템 찾기 (제거 전 정보 확인용)
                items = parse_market_file("market.txt")
                target_item = None
                for item in items:
                    if item.code.lower() == item_code.lower():
                        target_item = item
                        break
                
                if target_item is None:
                    await ctx.send(f"❌ 물품 코드 `{item_code}`를 찾을 수 없습니다.")
                    return
                
                # 아이템 제거
                success = remove_market_item("market.txt", item_code)
                
                if not success:
                    await ctx.send(f"❌ 물품 제거에 실패했습니다.")
                    return
                
                embed = discord.Embed(
                    title="✅ 물품 제거 완료",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="물품 이름",
                    value=f"**{target_item.name}**",
                    inline=False
                )
                embed.add_field(
                    name="물품 코드",
                    value=f"**{item_code}**",
                    inline=True
                )
                if target_item.is_role:
                    embed.add_field(
                        name="타입",
                        value="🎭 역할",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="타입",
                        value="🎫 티켓",
                        inline=True
                    )
                embed.add_field(
                    name="구매된 티켓/횟수",
                    value=f"**{target_item.tickets_sold}**",
                    inline=True
                )
                embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
                await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== !jk마켓 add 명령어 그룹 ==========
    @jk_market_group.group(name="add")
    @check_jk()
    async def jk_market_add_group(ctx):
        """JK 마켓 아이템 추가 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk마켓 add 티켓 [물품] [물품_코드] [뽑는_인원:1인당_구매가능] [가격]` 또는 `!jk마켓 add 역할 [역할_이름] [물품_코드] [가격]`")

    @jk_market_add_group.command(name="티켓")
    @check_jk()
    async def market_add_ticket_command(ctx, *args):
        """티켓 물품 추가"""
        if len(args) < 4:
            await ctx.send("❌ 사용법: `!jk마켓 add 티켓 [물품] [물품_코드] [뽑는_인원:1인당_구매가능] [가격]`\n예: `!jk마켓 add 티켓 스벅-아메리카노 ABC12345 3:5 50`")
            return
        
        # 마지막 3개 인자: 물품_코드, 뽑는_인원:1인당_구매가능, 가격
        # 나머지는 물품 이름
        draw_purchase = args[-2]
        try:
            price = int(args[-1])
        except ValueError:
            await ctx.send("❌ 가격은 숫자여야 합니다.")
            return
        
        item_code = args[-3]
        item_name = " ".join(args[:-3])  # 나머지가 물품 이름
        
        if not item_name:
            await ctx.send("❌ 물품 이름을 입력해주세요.")
            return
        
        if price < 0:
            await ctx.send("❌ 가격은 0 이상이어야 합니다.")
            return
        
        try:
            # 뽑는_인원:1인당_구매가능 파싱
            if ':' not in draw_purchase:
                await ctx.send("❌ 형식이 올바르지 않습니다. `뽑는_인원:1인당_구매가능` 형식으로 입력해주세요.\n예: `3:5`")
                return
            
            parts = draw_purchase.split(':', 1)
            try:
                draw_count = int(parts[0].strip())
                max_purchase = int(parts[1].strip())
            except ValueError:
                await ctx.send("❌ 뽑는 인원 수와 1인당 구매 가능 수는 숫자여야 합니다.")
                return
            
            if draw_count < 1 or max_purchase < 1:
                await ctx.send("❌ 뽑는 인원 수와 1인당 구매 가능 수는 1 이상이어야 합니다.")
                return
            
            # 파일 락 획득
            file_lock = await get_file_lock("market.txt")
            
            async with file_lock:
                # 새 아이템 생성
                new_item = MarketItem(
                    name=item_name,
                    code=item_code,
                    draw_count=draw_count,
                    max_purchase=max_purchase,
                    price_per_ticket=price,
                    quantity=0,  # 무제한
                    tickets_sold=0,
                    buyers=[],
                    is_role=False,
                    role_name=None
                )
                
                # 아이템 추가
                success = add_market_item("market.txt", new_item)
                
                if not success:
                    await ctx.send(f"❌ 물품 코드 `{item_code}`가 이미 존재합니다.")
                    return
                
                embed = discord.Embed(
                    title="✅ 티켓 물품 추가 완료",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="물품 이름",
                    value=f"**{item_name}**",
                    inline=False
                )
                embed.add_field(
                    name="물품 코드",
                    value=f"**{item_code}**",
                    inline=True
                )
                embed.add_field(
                    name="뽑는 인원",
                    value=f"**{draw_count}명**",
                    inline=True
                )
                embed.add_field(
                    name="1인당 최대 구매",
                    value=f"**{max_purchase}개**",
                    inline=True
                )
                embed.add_field(
                    name="티켓 가격",
                    value=f"**{price:,} 포인트**",
                    inline=True
                )
                embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
                await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_market_add_group.command(name="역할")
    @check_jk()
    async def market_add_role_command(ctx, *args):
        """역할 판매 추가"""
        if len(args) < 3:
            await ctx.send("❌ 사용법: `!jk마켓 add 역할 [역할_이름] [물품_코드] [가격]`\n예: `!jk마켓 add 역할 베타 테스터 BBEETTAA 10`")
            return
        
        # 마지막 2개 인자: 물품_코드, 가격
        # 나머지는 역할 이름
        try:
            price = int(args[-1])
        except ValueError:
            await ctx.send("❌ 가격은 숫자여야 합니다.")
            return
        
        item_code = args[-2]
        role_name = " ".join(args[:-2])  # 나머지가 역할 이름
        
        if not role_name:
            await ctx.send("❌ 역할 이름을 입력해주세요.")
            return
        
        if price < 0:
            await ctx.send("❌ 가격은 0 이상이어야 합니다.")
            return
        
        try:
            # 파일 락 획득
            file_lock = await get_file_lock("market.txt")
            
            async with file_lock:
                # 새 역할 아이템 생성
                new_item = MarketItem(
                    name=f"역할: {role_name}",
                    code=item_code,
                    draw_count=1,
                    max_purchase=1,  # 역할은 1인당 1개만 구매 가능
                    price_per_ticket=price,
                    quantity=0,  # 무제한
                    tickets_sold=0,
                    buyers=[],
                    is_role=True,
                    role_name=role_name
                )
                
                # 아이템 추가
                success = add_market_item("market.txt", new_item)
                
                if not success:
                    await ctx.send(f"❌ 물품 코드 `{item_code}`가 이미 존재합니다.")
                    return
                
                embed = discord.Embed(
                    title="✅ 역할 판매 추가 완료",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="역할 이름",
                    value=f"**{role_name}**",
                    inline=False
                )
                embed.add_field(
                    name="물품 코드",
                    value=f"**{item_code}**",
                    inline=True
                )
                embed.add_field(
                    name="가격",
                    value=f"**{price:,} 포인트**",
                    inline=True
                )
                embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
                await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== 에러 핸들러 ==========
    @market_list_command.error
    @market_clear_command.error
    @market_remove_command.error
    @market_add_ticket_command.error
    @market_add_role_command.error
    async def market_admin_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 인자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

