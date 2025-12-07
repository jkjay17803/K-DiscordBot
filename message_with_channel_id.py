# message_with_channel_id.py

import discord
from discord.ext import commands

def check_jk():
    async def predicate(ctx):
        return any(role.name == "JK" for role in ctx.author.roles)
    return commands.check(predicate)


def message_with_channel_id(bot):

    @bot.command(name="메시지")
    @check_jk()
    async def send_message(ctx, channel_id: int):

        messages = [msg async for msg in ctx.channel.history(limit=2)]
        if len(messages) < 2:
            await ctx.send("보낼 메시지가 없습니다.")
            return

        target_msg = messages[1]


        target_channel = bot.get_channel(channel_id)
        if target_channel is None:
            await ctx.send("채널을 찾을 수 없습니다. 채널 ID를 확인해주세요.")
            return


        await target_channel.send(target_msg.content)
        await ctx.send(f"{channel_id}번 채널로 메시지를 보냈습니다.")


    @send_message.error
    async def send_message_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("알 수 없는 오류")
