# voice_channel_exp_manager.py - 음성채널 EXP 설정 파일 관리

import os
from typing import Dict, Tuple, Optional
from pathlib import Path

VOICE_CHANNEL_EXP_FILE = "voice_channel_exp.txt"


def ensure_file():
    """파일이 없으면 생성"""
    if not os.path.exists(VOICE_CHANNEL_EXP_FILE):
        # 기본 설정이 있으면 파일 생성
        Path(VOICE_CHANNEL_EXP_FILE).touch()


def load_voice_channel_exp() -> Dict[int, Tuple[int, int]]:
    """
    voice_channel_exp.txt 파일에서 설정 로드
    Returns: {channel_id: (지급_주기_분, 지급_경험치)}
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
                
                # 형식: channel_id:n:m
                # 예: 123456789012345678:1:1
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) == 3:
                        try:
                            channel_id = int(parts[0].strip())
                            n = int(parts[1].strip())  # 지급 주기 (분)
                            m = int(parts[2].strip())  # 지급 경험치
                            result[channel_id] = (n, m)
                        except ValueError:
                            continue
    except Exception as e:
        print(f"[VoiceChannelExpManager] 파일 읽기 오류: {e}")
    
    return result


def save_voice_channel_exp(exp_settings: Dict[int, Tuple[int, int]]):
    """
    voice_channel_exp.txt 파일에 설정 저장
    Args:
        exp_settings: {channel_id: (지급_주기_분, 지급_경험치)}
    """
    ensure_file()
    
    try:
        with open(VOICE_CHANNEL_EXP_FILE, 'w', encoding='utf-8') as f:
            for channel_id, (n, m) in sorted(exp_settings.items()):
                f.write(f"{channel_id}:{n}:{m}\n")
    except Exception as e:
        print(f"[VoiceChannelExpManager] 파일 쓰기 오류: {e}")
        raise


def add_voice_channel_exp(channel_id: int, n: int, m: int) -> bool:
    """
    음성채널 EXP 설정 추가
    Returns: 성공 여부 (이미 존재하면 False)
    """
    settings = load_voice_channel_exp()
    
    if channel_id in settings:
        return False
    
    settings[channel_id] = (n, m)
    save_voice_channel_exp(settings)
    return True


def remove_voice_channel_exp(channel_id: int) -> bool:
    """
    음성채널 EXP 설정 제거
    Returns: 성공 여부 (존재하지 않으면 False)
    """
    settings = load_voice_channel_exp()
    
    if channel_id not in settings:
        return False
    
    del settings[channel_id]
    save_voice_channel_exp(settings)
    return True


def update_voice_channel_exp(channel_id: int, n: int, m: int) -> bool:
    """
    음성채널 EXP 설정 업데이트
    Returns: 성공 여부 (존재하지 않으면 False)
    """
    settings = load_voice_channel_exp()
    
    if channel_id not in settings:
        return False
    
    settings[channel_id] = (n, m)
    save_voice_channel_exp(settings)
    return True


def get_voice_channel_exp(channel_id: int) -> Optional[Tuple[int, int]]:
    """
    특정 채널의 EXP 설정 조회
    Returns: (지급_주기_분, 지급_경험치) 또는 None
    """
    settings = load_voice_channel_exp()
    return settings.get(channel_id)

