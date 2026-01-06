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
from role_manager import update_tier_role
from logger import send_levelup_log, send_tier_upgrade_log


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
        
        # 음성채널 입장 (처음 입장)
        if before.channel is None and after.channel is not None:
            await self._handle_voice_join(member, after.channel, guild_id, user_id)
        
        # 음성채널 퇴장 (완전히 나감)
        elif before.channel is not None and after.channel is None:
            await self._handle_voice_leave(member, before.channel, guild_id, user_id)
        
        # 음성채널 이동 (채널 간 이동)
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            # 이전 채널 퇴장 처리
            await self._handle_voice_leave(member, before.channel, guild_id, user_id)
            # 새로운 채널 입장 처리
            await self._handle_voice_join(member, after.channel, guild_id, user_id)
    
    def _get_channel_exp_settings(self, channel_id: int) -> tuple:
        """채널의 EXP 설정 반환 (지급_주기_분, 지급_경험치)"""
        if channel_id in VOICE_CHANNEL_EXP:
            return VOICE_CHANNEL_EXP[channel_id]
        return None  # 설정되지 않은 채널
    
    async def _handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, guild_id: int, user_id: int, silent: bool = False):
        """음성채널 입장 처리"""
        # 이미 세션이 있으면 무시 (이동인 경우)
        if user_id in self.active_sessions:
            return
        
        # 채널이 EXP 지급 채널인지 확인
        exp_settings = self._get_channel_exp_settings(channel.id)
        if exp_settings is None:
            if not silent:
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
        
        if not silent:
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
        """음성채널에 있는 동안 exp 누적 (06:00 ~ 23:59 사이만 지급)"""
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
                
                # 시간 체크: 06:00 ~ 23:59 사이만 경험치 지급
                current_time = datetime.now()
                current_hour = current_time.hour
                if not (6 <= current_hour < 24):
                    # 경험치 지급 시간이 아니면 스킵 (다음 체크까지 대기)
                    continue
                
                # exp 추가
                result = await add_exp(user_id, guild_id, exp_amount)
                
                # 레벨업 시 닉네임 업데이트, 역할 업데이트 및 로그 전송
                if result['leveled_up']:
                    await update_user_nickname(member, result['new_level'])
                    success, old_tier, new_tier = await update_tier_role(member, result['new_level'])
                    
                    # 티어 업그레이드 축하 메시지 전송
                    if success and old_tier and new_tier and old_tier != new_tier:
                        await send_tier_upgrade_log(self.bot, member, old_tier, new_tier, result['new_level'])
                    
                    # 음성채널 이름 가져오기
                    channel_name = "알 수 없음"
                    if member.voice and member.voice.channel:
                        channel_name = member.voice.channel.name
                    
                    await send_levelup_log(
                        self.bot,
                        member,
                        result['old_level'],
                        result['new_level'],
                        result['points_earned'],
                        result['new_points'],
                        f"🎤 {channel_name}"
                    )
                    print(f"[VoiceMonitor] {member.name} leveled up to {result['new_level']}!")
                
        except asyncio.CancelledError:
            # 작업이 취소되었을 때 (퇴장 시)
            pass
        except Exception as e:
            print(f"[VoiceMonitor] Error in exp accumulation for {member.name}: {e}")
    
    async def initialize_existing_voice_users(self):
        """봇 시작 시 이미 음성채널에 있는 사용자들을 초기화"""
        initialized_count = 0
        initialized_users = []
        
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
                        await self._handle_voice_join(member, channel, guild.id, member.id, silent=True)
                        initialized_count += 1
                        initialized_users.append(member.name)
                    except Exception as e:
                        print(f"[VoiceMonitor] 초기화 실패: {member.name} - {e}")
        
        # 이미 이용중인 사용자 목록 출력
        if initialized_users:
            print(f"[VoiceMonitor] 이미 이용중인 사용자 확인: {', '.join(initialized_users)}")
        
        print(f"[VoiceMonitor] 초기화 완료. {initialized_count}명의 새로운 사용자 세션 시작.")
    
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
