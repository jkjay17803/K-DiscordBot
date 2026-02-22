# voice_monitor.py - 음성채널 모니터링 및 exp 획득

import asyncio
from datetime import datetime, timedelta
from typing import Dict
import discord

from config import VOICE_CHANNEL_EXP
from voice_channel_exp_manager import load_voice_channel_exp
from database import (
    create_voice_session, end_voice_session,
    update_last_voice_join
)
from level_system import add_exp
from exp_ignore_manager import is_ignored as exp_is_ignored
from nickname_manager import sync_level_display
from role_manager import get_tier_for_level
from logger import send_levelup_log, send_tier_upgrade_log
from warning_system import check_warning_restrictions
from utils import has_jk_role


class VoiceMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: Dict[int, Dict] = {}  # {user_id: {guild_id, channel_id, session_id, join_time, task}}
        self.exp_tasks: Dict[int, asyncio.Task] = {}  # {user_id: task}
        self.processing_users: set = set()  # 처리 중인 사용자 (재귀 호출 방지)
    
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
        """채널의 EXP 설정 반환 (지급_주기_분, 지급_경험치, 시작_시, 종료_시)"""
        file_settings = load_voice_channel_exp()
        if channel_id in file_settings:
            return file_settings[channel_id]
        if channel_id in VOICE_CHANNEL_EXP:
            v = VOICE_CHANNEL_EXP[channel_id]
            return (v[0], v[1], v[2] if len(v) > 2 else 6, v[3] if len(v) > 3 else 24)
        return None
    
    async def _handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, guild_id: int, user_id: int, silent: bool = False):
        """음성채널 입장 처리"""
        # 처리 중인 사용자는 무시 (재귀 호출 방지)
        if user_id in self.processing_users:
            return
        
        # 처리 시작 플래그 설정
        self.processing_users.add(user_id)
        
        try:
            # 이미 세션이 있으면 이전 세션 종료 (채널 이동 시 새로 시작)
            if user_id in self.active_sessions:
                # 이전 세션 정리
                old_session = self.active_sessions[user_id]
                old_channel_id = old_session['channel_id']
                old_channel = member.guild.get_channel(old_channel_id)
                if old_channel:
                    await self._handle_voice_leave(member, old_channel, guild_id, user_id)
            
            # JK 역할을 가진 사용자는 제한 없음
            user_has_jk = has_jk_role(member)
            
            # 경고 체크 (JK 권한이 없을 때만)
            if not user_has_jk:
                restrictions = await check_warning_restrictions(user_id, guild_id)
                if not restrictions['can_use_voice']:
                    # 음성 채널에서 강제로 퇴장
                    try:
                        await member.move_to(None, reason=f"경고 {restrictions['warning_count']}회로 음성 채팅방 이용 불가")
                        if not silent:
                            await channel.send(
                                f"{member.mention} 경고 7회 이상으로 음성 채팅방을 이용할 수 없습니다. (현재 경고: {restrictions['warning_count']}회)",
                                delete_after=10
                            )
                    except discord.Forbidden:
                        if not silent:
                            print(f"[VoiceMonitor] {member.name}는 경고 {restrictions['warning_count']}회로 음성 채팅방 이용 불가 (강제 퇴장 권한 없음)")
                    except Exception as e:
                        print(f"[VoiceMonitor] 음성 채널 강제 퇴장 중 오류: {e}")
                    finally:
                        # 강제 퇴장 후 플래그 제거 (퇴장 이벤트가 처리될 시간 확보)
                        async def remove_flag():
                            await asyncio.sleep(0.5)  # 0.5초 딜레이
                            self.processing_users.discard(user_id)
                        asyncio.create_task(remove_flag())
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
            
            # 상호작용 시점에 DB 기준으로 닉네임/역할 동기화 (레벨업 반영)
            await sync_level_display(member)
            
            # 세션 생성
            session_id = await create_voice_session(user_id, guild_id, channel.id)
            await update_last_voice_join(user_id, guild_id)
            
            # 세션 정보 저장 (시작/종료 시 포함)
            self.active_sessions[user_id] = {
                'guild_id': guild_id,
                'channel_id': channel.id,
                'session_id': session_id,
                'join_time': datetime.now(),
                'member': member,
                'exp_interval': exp_settings[0],
                'exp_amount': exp_settings[1],
                'exp_start_hour': exp_settings[2],
                'exp_end_hour': exp_settings[3],
            }
            
            task = asyncio.create_task(self._accumulate_exp(user_id, guild_id, member))
            self.exp_tasks[user_id] = task
            
            if not silent:
                print(f"[VoiceMonitor] {member.name} joined voice channel {channel.name} in {member.guild.name} (EXP 설정: {exp_settings[0]}분마다 {exp_settings[1]} exp, {exp_settings[2]:02d}:00~{exp_settings[3]:02d}:00)")
        
        finally:
            # 정상 처리 완료 시 플래그 제거 (강제 퇴장이 아닌 경우)
            # 강제 퇴장은 위에서 이미 처리됨
            if user_id in self.processing_users:
                self.processing_users.discard(user_id)
    
    async def _handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel, guild_id: int, user_id: int):
        """음성채널 퇴장 처리"""
        if user_id not in self.active_sessions:
            return
        
        session_info = self.active_sessions[user_id]
        session_id = session_info['session_id']
        
        # exp 누적 작업 중지 (취소 후 완료 대기)
        if user_id in self.exp_tasks:
            task = self.exp_tasks[user_id]
            task.cancel()
            # 작업이 완전히 취소될 때까지 대기 (중복 EXP 지급 방지)
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.exp_tasks[user_id]
        
        # 세션 종료 (보정 지급 없음 - 지급 주기를 채우지 않고 퇴장하면 0exp)
        exp_earned = 0
        
        # 세션 종료 기록
        await end_voice_session(session_id, exp_earned)
        
        # 세션 정보 제거
        del self.active_sessions[user_id]
        
        # 처리 중 플래그 제거 (퇴장 시)
        self.processing_users.discard(user_id)
        
        print(f"[VoiceMonitor] {member.name} left voice channel {channel.name} in {member.guild.name} (earned {exp_earned} exp)")
    
    async def _accumulate_exp(self, user_id: int, guild_id: int, member: discord.Member):
        """음성채널에 있는 동안 exp 누적 (06:00 ~ 23:59 사이만 지급)"""
        try:
            # 세션 정보에서 EXP 설정 가져오기
            if user_id not in self.active_sessions:
                return
            
            session_info = self.active_sessions[user_id]
            exp_interval = session_info.get('exp_interval', 1)
            exp_amount = session_info.get('exp_amount', 1)
            start_hour = session_info.get('exp_start_hour', 6)
            end_hour = session_info.get('exp_end_hour', 24)
            
            check_interval = exp_interval * 60
            
            while True:
                await asyncio.sleep(check_interval)
                
                if user_id not in self.active_sessions:
                    break
                if member.voice is None or member.voice.channel is None:
                    break
                current_channel_id = member.voice.channel.id
                if current_channel_id != session_info['channel_id']:
                    break
                
                # 채널별 지급 시간: start_hour <= current_hour < end_hour
                current_time = datetime.now()
                current_hour = current_time.hour
                if not (start_hour <= current_hour < end_hour):
                    continue
                
                # EXP 지급 제외 사용자는 스킵
                if exp_is_ignored(guild_id, user_id):
                    continue
                
                # exp 추가 (트랜잭션 모드)
                result = await add_exp(user_id, guild_id, exp_amount, use_transaction=True)
                db = result.get('db')
                
                # exp는 항상 먼저 커밋 (Discord API 실패해도 지급분은 유지)
                if db:
                    await db.commit()
                    await db.close()
                
                # 레벨업 시 로그만 전송. 닉네임/역할은 음성 입장·채팅 등 상호작용 시 sync_level_display로 반영
                if result['leveled_up']:
                    try:
                        old_t = get_tier_for_level(result['old_level'])
                        new_t = get_tier_for_level(result['new_level'])
                        old_tier = old_t[0] if old_t else None
                        new_tier = new_t[0] if new_t else None
                        if old_tier != new_tier:
                            await send_tier_upgrade_log(self.bot, member, old_tier or "", new_tier or "", result['new_level'])
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
                        # 레벨업 시 별명·칭호 즉시 반영
                        try:
                            await sync_level_display(member)
                        except Exception as sync_err:
                            print(f"[VoiceMonitor] 레벨업 후 별명/칭호 갱신 실패: {member.name} - {sync_err}")
                    except Exception as e:
                        print(f"[VoiceMonitor] 레벨업 로그 전송 실패: {member.name} - {e}")
                
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
    
    async def ensure_sessions_for_guild(self, guild: discord.Guild):
        """특정 길드의 EXP 채널에 있는 멤버가 누락됐을 때 세션 보정 (참여 현황 표시 전 호출)"""
        for channel in guild.voice_channels:
            exp_settings = self._get_channel_exp_settings(channel.id)
            if exp_settings is None:
                continue
            for member in channel.members:
                if member.bot:
                    continue
                # 세션이 없거나, 다른 채널용 세션이면 지금 채널 기준으로 세션 생성/갱신
                if member.id not in self.active_sessions or self.active_sessions[member.id]['channel_id'] != channel.id:
                    try:
                        await self._handle_voice_join(member, channel, guild.id, member.id, silent=True)
                    except Exception as e:
                        print(f"[VoiceMonitor] 세션 보정 실패: {member.name} - {e}")
    
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
