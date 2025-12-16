# voice_monitor.py - 음성채널 모니터링 및 exp 획득

import asyncio
from datetime import datetime
from typing import Dict
import discord

from config import VOICE_CHANNEL_EXP
from database import (
    create_voice_session, end_voice_session,
    update_last_voice_join
)
from level_system import add_exp
from nickname_manager import update_user_nickname
from logger import send_levelup_log


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
    
    def _get_channel_exp_settings(self, channel_id: int) -> tuple:
        """채널의 EXP 설정 반환 (지급_주기_분, 지급_경험치)"""
        if channel_id in VOICE_CHANNEL_EXP:
            return VOICE_CHANNEL_EXP[channel_id]
        return None  # 설정되지 않은 채널
    
    async def _handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, guild_id: int, user_id: int):
        """음성채널 입장 처리"""
        # 이미 세션이 있으면 무시 (이동인 경우)
        if user_id in self.active_sessions:
            return
        
        # 채널이 EXP 지급 채널인지 확인
        exp_settings = self._get_channel_exp_settings(channel.id)
        if exp_settings is None:
            print(f"[VoiceMonitor] {member.name} joined voice channel {channel.name} (EXP 지급 채널 아님)")
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
            'member': member,
            'exp_interval': exp_settings[0],  # 지급 주기 (분)
            'exp_amount': exp_settings[1]     # 지급 경험치
        }
        
        # exp 누적 작업 시작
        task = asyncio.create_task(self._accumulate_exp(user_id, guild_id, member))
        self.exp_tasks[user_id] = task
        
        print(f"[VoiceMonitor] {member.name} joined voice channel {channel.name} in {member.guild.name} (EXP 설정: {exp_settings[0]}분마다 {exp_settings[1]} exp)")
    
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
        
        # 세션 종료 시간 계산 (채널별 설정 사용)
        join_time = session_info['join_time']
        duration = datetime.now() - join_time
        minutes = duration.total_seconds() / 60
        
        # 채널별 EXP 설정 사용
        exp_settings = self._get_channel_exp_settings(channel.id)
        if exp_settings:
            exp_interval = exp_settings[0]  # 지급 주기 (분)
            exp_amount = exp_settings[1]     # 지급 경험치
            # 지급 주기 단위로 계산
            exp_earned = int(minutes / exp_interval) * exp_amount
        else:
            # 설정되지 않은 채널 (이론적으로는 여기 도달하지 않아야 함)
            exp_earned = 0
        
        # 세션 종료 기록
        await end_voice_session(session_id, exp_earned)
        
        # 세션 정보 제거
        del self.active_sessions[user_id]
        
        print(f"[VoiceMonitor] {member.name} left voice channel {channel.name} in {member.guild.name} (earned {exp_earned} exp)")
    
    async def _accumulate_exp(self, user_id: int, guild_id: int, member: discord.Member):
        """음성채널에 있는 동안 exp 누적"""
        try:
            # 세션 정보에서 EXP 설정 가져오기
            if user_id not in self.active_sessions:
                return
            
            session_info = self.active_sessions[user_id]
            exp_interval = session_info.get('exp_interval', 1)  # 지급 주기 (분)
            exp_amount = session_info.get('exp_amount', 1)       # 지급 경험치
            
            # 지급 주기를 초 단위로 변환
            check_interval = exp_interval * 60
            
            while True:
                await asyncio.sleep(check_interval)
                
                # 세션이 여전히 활성화되어 있는지 확인
                if user_id not in self.active_sessions:
                    break
                
                # 사용자가 여전히 음성채널에 있는지 확인
                if member.voice is None or member.voice.channel is None:
                    break
                
                # 현재 채널이 여전히 EXP 지급 채널인지 확인
                current_channel_id = member.voice.channel.id
                if current_channel_id != session_info['channel_id']:
                    # 채널이 변경되었으면 새 채널 설정 확인
                    new_exp_settings = self._get_channel_exp_settings(current_channel_id)
                    if new_exp_settings is None:
                        break
                    # 새 채널 설정으로 업데이트
                    session_info['channel_id'] = current_channel_id
                    session_info['exp_interval'] = new_exp_settings[0]
                    session_info['exp_amount'] = new_exp_settings[1]
                    exp_interval = new_exp_settings[0]
                    exp_amount = new_exp_settings[1]
                    check_interval = exp_interval * 60
                
                # exp 추가
                result = await add_exp(user_id, guild_id, exp_amount)
                
                # 레벨업 시 닉네임 업데이트 및 로그 전송
                if result['leveled_up']:
                    await update_user_nickname(member, result['new_level'])
                    await send_levelup_log(
                        self.bot,
                        member,
                        result['old_level'],
                        result['new_level'],
                        result['points_earned'],
                        result['new_points'],
                        "음성채널"
                    )
                    print(f"[VoiceMonitor] {member.name} leveled up to {result['new_level']}!")
                
        except asyncio.CancelledError:
            # 작업이 취소되었을 때 (퇴장 시)
            pass
        except Exception as e:
            print(f"[VoiceMonitor] Error in exp accumulation for {member.name}: {e}")
    
    async def initialize_existing_voice_users(self):
        """봇 시작 시 이미 음성채널에 있는 사용자들을 초기화"""
        print("[VoiceMonitor] 초기화: 이미 음성채널에 있는 사용자 확인 중...")
        initialized_count = 0
        skipped_count = 0
        
        for guild in self.bot.guilds:
            # 서버의 모든 음성채널 확인
            for channel in guild.voice_channels:
                # 채널이 EXP 지급 채널인지 확인
                exp_settings = self._get_channel_exp_settings(channel.id)
                if exp_settings is None:
                    continue  # EXP 지급 채널이 아니면 스킵
                
                # 채널에 있는 모든 멤버 확인
                for member in channel.members:
                    # 봇은 무시
                    if member.bot:
                        continue
                    
                    # 이미 세션이 있으면 스킵
                    if member.id in self.active_sessions:
                        continue
                    
                    # 사용자 초기화
                    try:
                        await self._handle_voice_join(member, channel, guild.id, member.id)
                        initialized_count += 1
                        print(f"[VoiceMonitor] 초기화: {member.name}가 이미 {channel.name}에 있음")
                    except Exception as e:
                        skipped_count += 1
                        print(f"[VoiceMonitor] 초기화 실패: {member.name} - {e}")
        
        print(f"[VoiceMonitor] 초기화 완료: {initialized_count}명의 사용자 세션 시작, {skipped_count}명 스킵")
    
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
