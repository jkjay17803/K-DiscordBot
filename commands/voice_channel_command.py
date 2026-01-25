# commands/voice_channel_command.py - JK 음성채널 EXP 설정 명령어

import discord
from discord.ext import commands
from datetime import datetime
from voice_channel_exp_manager import (
    load_voice_channel_exp, add_voice_channel_exp,
    remove_voice_channel_exp, update_voice_channel_exp
)
from utils import has_jk_role


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


def voice_channel_command(k):

    # ========== !jk음성채팅 명령어 그룹 ==========
    @k.group(name="jk음성채팅")
    @check_jk()
    async def jk_voice_channel_group(ctx):
        """JK 음성채널 EXP 설정 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk음성채팅 리스트` 또는 `!jk음성채팅 add [음성채널_id] [n]:[m]` 또는 `!jk음성채팅 remove [음성채널_id]`")

    @jk_voice_channel_group.command(name="리스트")
    @check_jk()
    async def voice_channel_list_command(ctx):
        """음성채널 EXP 설정 목록 조회"""
        try:
            settings = load_voice_channel_exp()
            
            if not settings:
                await ctx.send("❌ 등록된 음성채널 EXP 설정이 없습니다.")
                return
            
            embed = discord.Embed(
                title="📋 음성채널 EXP 설정 목록",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for idx, (channel_id, (n, m)) in enumerate(sorted(settings.items()), 1):
                # 채널 정보 가져오기
                channel = ctx.bot.get_channel(channel_id)
                if channel:
                    channel_name = f"{channel.name} ({channel.mention})"
                else:
                    channel_name = f"ID: {channel_id} (채널을 찾을 수 없음)"
                
                embed.add_field(
                    name=f"{idx}. {channel_name}",
                    value=f"**지급 주기:** {n}분마다\n**지급 경험치:** {m} exp",
                    inline=False
                )
            
            embed.set_footer(text=f"총 {len(settings)}개의 채널 설정")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_voice_channel_group.command(name="add")
    @check_jk()
    async def voice_channel_add_command(ctx, channel_id: int = None, exp_settings: str = None):
        """음성채널 EXP 설정 추가"""
        if channel_id is None or exp_settings is None:
            await ctx.send("❌ 사용법: `!jk음성채팅 add [음성채널_id] [n]:[m]`\n예: `!jk음성채팅 add 123456789012345678 5:10` (5분마다 10 exp 지급)")
            return
        
        # n:m 형식 파싱
        if ':' not in exp_settings:
            await ctx.send("❌ 형식이 올바르지 않습니다. `n:m` 형식으로 입력해주세요.\n예: `5:10` (5분마다 10 exp 지급)")
            return
        
        try:
            parts = exp_settings.split(':', 1)
            n = int(parts[0].strip())  # 지급 주기 (분)
            m = int(parts[1].strip())  # 지급 경험치
        except ValueError:
            await ctx.send("❌ 지급 주기와 경험치는 숫자여야 합니다.")
            return
        
        if n < 1 or m < 1:
            await ctx.send("❌ 지급 주기와 경험치는 1 이상이어야 합니다.")
            return
        
        try:
            # 채널 존재 확인
            channel = ctx.bot.get_channel(channel_id)
            if channel is None:
                await ctx.send(f"❌ 음성채널 ID `{channel_id}`를 찾을 수 없습니다.")
                return
            
            if not isinstance(channel, discord.VoiceChannel):
                await ctx.send(f"❌ `{channel_id}`는 음성채널이 아닙니다.")
                return
            
            # 이미 존재하는지 확인
            existing = load_voice_channel_exp()
            if channel_id in existing:
                # 업데이트
                success = update_voice_channel_exp(channel_id, n, m)
                action = "업데이트"
            else:
                # 추가
                success = add_voice_channel_exp(channel_id, n, m)
                action = "추가"
            
            if not success:
                await ctx.send(f"❌ 설정 {action}에 실패했습니다.")
                return
            
            embed = discord.Embed(
                title=f"✅ 음성채널 EXP 설정 {action} 완료",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="음성채널",
                value=f"{channel.name} ({channel.mention})",
                inline=False
            )
            embed.add_field(
                name="채널 ID",
                value=f"**{channel_id}**",
                inline=True
            )
            embed.add_field(
                name="지급 주기",
                value=f"**{n}분마다**",
                inline=True
            )
            embed.add_field(
                name="지급 경험치",
                value=f"**{m} exp**",
                inline=True
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_voice_channel_group.command(name="remove")
    @check_jk()
    async def voice_channel_remove_command(ctx, channel_id: int = None):
        """음성채널 EXP 설정 제거"""
        if channel_id is None:
            await ctx.send("❌ 사용법: `!jk음성채팅 remove [음성채널_id]`\n예: `!jk음성채팅 remove 123456789012345678`")
            return
        
        try:
            # 채널 존재 확인
            channel = ctx.bot.get_channel(channel_id)
            channel_name = f"ID: {channel_id}"
            if channel:
                channel_name = f"{channel.name} ({channel.mention})"
            
            # 설정 확인
            settings = load_voice_channel_exp()
            if channel_id not in settings:
                await ctx.send(f"❌ 음성채널 ID `{channel_id}`에 대한 EXP 설정이 없습니다.")
                return
            
            # 제거
            success = remove_voice_channel_exp(channel_id)
            
            if not success:
                await ctx.send(f"❌ 설정 제거에 실패했습니다.")
                return
            
            removed_settings = settings[channel_id]
            
            embed = discord.Embed(
                title="✅ 음성채널 EXP 설정 제거 완료",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="음성채널",
                value=channel_name,
                inline=False
            )
            embed.add_field(
                name="채널 ID",
                value=f"**{channel_id}**",
                inline=True
            )
            embed.add_field(
                name="제거된 설정",
                value=f"{removed_settings[0]}분마다 {removed_settings[1]} exp",
                inline=True
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== 에러 핸들러 ==========
    @voice_channel_list_command.error
    @voice_channel_add_command.error
    @voice_channel_remove_command.error
    async def voice_channel_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 인자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

