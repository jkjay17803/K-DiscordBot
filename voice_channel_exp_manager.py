# voice_channel_exp_manager.py - 음성채널 EXP 설정 파일 관리

import os
from typing import Dict, Tuple, Optional
from pathlib import Path

VOICE_CHANNEL_EXP_FILE = "voice_channel_exp.txt"

# 기본 EXP 지급 시간: 06:00 ~ 23:59 (start_hour=6, end_hour=24는 24 미만이므로 23:59까지)
DEFAULT_START_HOUR = 6
DEFAULT_END_HOUR = 24


def _normalize_settings(value: Tuple) -> Tuple[int, int, int, int]:
    """(n, m) 또는 (n, m, start, end) → (n, m, start_hour, end_hour)"""
    if len(value) == 2:
        return (value[0], value[1], DEFAULT_START_HOUR, DEFAULT_END_HOUR)
    if len(value) >= 4:
        return (value[0], value[1], value[2], value[3])
    return (value[0], value[1], DEFAULT_START_HOUR, DEFAULT_END_HOUR)


def ensure_file():
    """파일이 없으면 생성"""
    if not os.path.exists(VOICE_CHANNEL_EXP_FILE):
        Path(VOICE_CHANNEL_EXP_FILE).touch()


def load_voice_channel_exp() -> Dict[int, Tuple[int, int, int, int]]:
    """
    voice_channel_exp.txt 파일에서 설정 로드
    Returns: {channel_id: (지급_주기_분, 지급_경험치, 시작_시, 종료_시)}
    종료_시는 미포함(24면 23:59까지)
    """
    ensure_file()
    result = {}
    if not os.path.exists(VOICE_CHANNEL_EXP_FILE):
        return result
    try:
        with open(VOICE_CHANNEL_EXP_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    parts = [p.strip() for p in line.split(':')]
                    if len(parts) >= 3:
                        try:
                            channel_id = int(parts[0])
                            n = int(parts[1])
                            m = int(parts[2])
                            start_h = int(parts[3]) if len(parts) > 3 else DEFAULT_START_HOUR
                            end_h = int(parts[4]) if len(parts) > 4 else DEFAULT_END_HOUR
                            result[channel_id] = (n, m, start_h, end_h)
                        except (ValueError, IndexError):
                            continue
    except Exception as e:
        print(f"[VoiceChannelExpManager] 파일 읽기 오류: {e}")
    return result


def save_voice_channel_exp(exp_settings: Dict[int, Tuple[int, int, int, int]]):
    """
    voice_channel_exp.txt 파일에 설정 저장
    Args:
        exp_settings: {channel_id: (지급_주기_분, 지급_경험치, 시작_시, 종료_시)}
    """
    ensure_file()
    try:
        with open(VOICE_CHANNEL_EXP_FILE, 'w', encoding='utf-8') as f:
            for channel_id, tup in sorted(exp_settings.items()):
                n, m, start_h, end_h = _normalize_settings(tup)
                f.write(f"{channel_id}:{n}:{m}:{start_h}:{end_h}\n")
    except Exception as e:
        print(f"[VoiceChannelExpManager] 파일 쓰기 오류: {e}")
        raise


def add_voice_channel_exp(
    channel_id: int,
    n: int,
    m: int,
    start_hour: int = DEFAULT_START_HOUR,
    end_hour: int = DEFAULT_END_HOUR,
) -> bool:
    """
    음성채널 EXP 설정 추가
    start_hour: 지급 시작 시(0~23), end_hour: 지급 종료 시(1~24, 미포함)
    Returns: 성공 여부 (이미 존재하면 False)
    """
    settings = load_voice_channel_exp()
    if channel_id in settings:
        return False
    settings[channel_id] = (n, m, start_hour, end_hour)
    save_voice_channel_exp(settings)
    return True


def remove_voice_channel_exp(channel_id: int) -> bool:
    """음성채널 EXP 설정 제거. Returns: 성공 여부"""
    settings = load_voice_channel_exp()
    if channel_id not in settings:
        return False
    del settings[channel_id]
    save_voice_channel_exp(settings)
    return True


def update_voice_channel_exp(
    channel_id: int,
    n: int,
    m: int,
    start_hour: int = DEFAULT_START_HOUR,
    end_hour: int = DEFAULT_END_HOUR,
) -> bool:
    """음성채널 EXP 설정 업데이트. Returns: 성공 여부"""
    settings = load_voice_channel_exp()
    if channel_id not in settings:
        return False
    settings[channel_id] = (n, m, start_hour, end_hour)
    save_voice_channel_exp(settings)
    return True


def get_voice_channel_exp(channel_id: int) -> Optional[Tuple[int, int, int, int]]:
    """
    특정 채널의 EXP 설정 조회
    Returns: (지급_주기_분, 지급_경험치, 시작_시, 종료_시) 또는 None
    """
    settings = load_voice_channel_exp()
    val = settings.get(channel_id)
    return _normalize_settings(val) if val else None
