# voice_monitor.py - 음성채널 모니터링 및 exp 획득

import asyncio
from datetime import datetime, timedelta
from typing import Dict
import discord

from config import EXP_PER_MINUTE, VOICE_CHECK_INTERVAL
from database import (
    get_or_create_user, create_voice_session, end_voice_session,
    update_last_voice_join
)
from level_system import add_exp
from nickname_manager import update_user_nickname


class VoiceMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: Dict[int, Dict] = {}  # {user_id: {guild_id, channel_id, session_id, join_time, task}}
        self.exp_tasks: Dict[int, asyncio.Task] = {}  # {user_id: task}
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """음성채널 상태 변경 감지"""
        # 봇 자신은 무시
        if member.bot:
            return
        
        guild_id = member.guild.id
        user_id = member.id
        
        # 음성채널 입장
        if before.channel is None and after.channel is not None:
            await self._handle_voice_join(member, after.channel, guild_id, user_id)
        
        # 음성채널 퇴장 또는 이동
        elif before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
            await self._handle_voice_leave(member, before.channel, guild_id, user_id)
    
    async def _handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, guild_id: int, user_id: int):
        """음성채널 입장 처리"""
        # 이미 세션이 있으면 무시 (이동인 경우)
        if user_id in self.active_sessions:
            return
        
        # 사용자 데이터가 없으면 생성 (처음 입장하는 사용자)
        from database import get_or_create_user
        await get_or_create_user(user_id, guild_id)
        
        # 세션 생성
        session_id = await create_voice_session(user_id, guild_id, channel.id)
        await update_last_voice_join(user_id, guild_id)
        
        # 세션 정보 저장
        self.active_sessions[user_id] = {
            'guild_id': guild_id,
            'channel_id': channel.id,
            'session_id': session_id,
            'join_time': datetime.now(),
            'member': member
        }
        
        # exp 누적 작업 시작
        task = asyncio.create_task(self._accumulate_exp(user_id, guild_id, member))
        self.exp_tasks[user_id] = task
        
        print(f"[VoiceMonitor] {member.name} joined voice channel {channel.name} in {member.guild.name}")
    
    async def _handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel, guild_id: int, user_id: int):
        """음성채널 퇴장 처리"""
        if user_id not in self.active_sessions:
            return
        
        session_info = self.active_sessions[user_id]
        session_id = session_info['session_id']
        
        # exp 누적 작업 중지
        if user_id in self.exp_tasks:
            task = self.exp_tasks[user_id]
            task.cancel()
            del self.exp_tasks[user_id]
        
        # 세션 종료 시간 계산
        join_time = session_info['join_time']
        duration = datetime.now() - join_time
        minutes = duration.total_seconds() / 60
        exp_earned = int(minutes * EXP_PER_MINUTE)
        
        # 세션 종료 기록
        await end_voice_session(session_id, exp_earned)
        
        # 세션 정보 제거
        del self.active_sessions[user_id]
        
        print(f"[VoiceMonitor] {member.name} left voice channel {channel.name} in {member.guild.name} (earned {exp_earned} exp)")
    
    async def _accumulate_exp(self, user_id: int, guild_id: int, member: discord.Member):
        """음성채널에 있는 동안 exp 누적"""
        try:
            while True:
                await asyncio.sleep(VOICE_CHECK_INTERVAL)
                
                # 세션이 여전히 활성화되어 있는지 확인
                if user_id not in self.active_sessions:
                    break
                
                # 사용자가 여전히 음성채널에 있는지 확인
                if member.voice is None or member.voice.channel is None:
                    break
                
                # exp 추가
                result = await add_exp(user_id, guild_id, EXP_PER_MINUTE)
                
                # 레벨업 시 닉네임 업데이트
                if result['leveled_up']:
                    await update_user_nickname(member, result['new_level'])
                    print(f"[VoiceMonitor] {member.name} leveled up to {result['new_level']}!")
                
        except asyncio.CancelledError:
            # 작업이 취소되었을 때 (퇴장 시)
            pass
        except Exception as e:
            print(f"[VoiceMonitor] Error in exp accumulation for {member.name}: {e}")
    
    def get_active_users(self) -> list:
        """현재 음성채널에 있는 사용자 목록 반환"""
        return list(self.active_sessions.keys())


def setup_voice_monitor(bot):
    """음성 모니터 설정"""
    monitor = VoiceMonitor(bot)
    
    @bot.event
    async def on_voice_state_update(member, before, after):
        await monitor.on_voice_state_update(member, before, after)
    
    return monitor

