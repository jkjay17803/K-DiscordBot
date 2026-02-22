# message_with_channel_id.py

import time
import discord
from discord.ext import commands
from warning_system import check_warning_restrictions
from utils import has_jk_role
from nickname_manager import sync_level_display

# 채팅 시 레벨 표시 동기화 쓰로틀: (user_id, guild_id) -> 마지막 동기화 시각
_last_level_sync: dict[tuple[int, int], float] = {}
_SYNC_COOLDOWN_SEC = 300  # 5분

def check_jk():
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


def message_with_channel_id(k):

    @k.command(name="메시지")
    @check_jk()
    async def send_message(ctx, channel_id: int):

        messages = [msg async for msg in ctx.channel.history(limit=2)]
        if len(messages) < 2:
            await ctx.send("보낼 메시지가 없습니다.")
            return

        target_msg = messages[1]


        target_channel = k.get_channel(channel_id)
        if target_channel is None:
            await ctx.send("채널을 찾을 수 없습니다. 채널 ID를 확인해주세요.")
            return


        await target_channel.send(target_msg.content)
        await ctx.send(f"{channel_id}번 채널로 메시지를 보냈습니다.")


    @send_message.error
    async def send_message_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("알 수 없는 오류")

    # 메시지 전송 제한 (경고 3회 이상)
    @k.event
    async def on_message(message):
        # 봇 메시지는 무시
        if message.author.bot:
            await k.process_commands(message)
            return
        
        # 명령어는 처리되도록 함 (명령어는 제한 없음)
        if message.content.startswith('!'):
            await k.process_commands(message)
            return
        
        # 상호작용 시점에 레벨 표시(닉네임/역할) 동기화 (5분당 1회)
        if message.guild:
            key = (message.author.id, message.guild.id)
            now = time.time()
            if now - _last_level_sync.get(key, 0) >= _SYNC_COOLDOWN_SEC:
                try:
                    await sync_level_display(message.author)
                    _last_level_sync[key] = now
                except Exception:
                    pass
        
        # JK 역할을 가진 사용자는 제한 없음
        if has_jk_role(message.author):
            await k.process_commands(message)
            return
        
        # 경고 체크
        restrictions = await check_warning_restrictions(message.author.id, message.guild.id)
        
        if not restrictions['can_send_messages']:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} 경고 3회 이상으로 메시지를 보낼 수 없습니다. (현재 경고: {restrictions['warning_count']}회)",
                    delete_after=5
                )
            except discord.Forbidden:
                # 메시지 삭제 권한이 없으면 무시
                pass
            except Exception as e:
                print(f"[WarningSystem] 메시지 삭제 중 오류: {e}")
        
        # 명령어 처리 (경고 체크 후에도 명령어는 처리되어야 함)
        await k.process_commands(message)
