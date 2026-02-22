# exp_ignore_manager.py - EXP 지급 제외 사용자 목록 관리 (길드별)

import json
import os
from typing import Dict, Set

EXP_IGNORE_FILE = "exp_ignore.json"


def _load_raw() -> Dict[str, list]:
    """파일에서 {guild_id: [user_id, ...]} 로드 (키는 문자열)"""
    if not os.path.exists(EXP_IGNORE_FILE):
        return {}
    try:
        with open(EXP_IGNORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[ExpIgnoreManager] 로드 오류: {e}")
        return {}


def _save_raw(data: Dict[str, list]):
    """파일에 저장"""
    try:
        with open(EXP_IGNORE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ExpIgnoreManager] 저장 오류: {e}")


def get_ignored_set(guild_id: int) -> Set[int]:
    """해당 길드에서 EXP 지급 제외된 user_id 집합 반환"""
    raw = _load_raw()
    key = str(guild_id)
    if key not in raw or not isinstance(raw[key], list):
        return set()
    return set(int(uid) for uid in raw[key] if isinstance(uid, (int, str)) and str(uid).isdigit())


def is_ignored(guild_id: int, user_id: int) -> bool:
    """해당 길드에서 해당 사용자가 EXP 제외인지 여부"""
    return user_id in get_ignored_set(guild_id)


def toggle_ignore(guild_id: int, user_id: int) -> bool:
    """
    EXP 지급 제외 토글.
    Returns: True = 이제 제외됨(지급 안 함), False = 이제 지급받음(제외 해제)
    """
    raw = _load_raw()
    key = str(guild_id)
    if key not in raw:
        raw[key] = []
    current = set(int(uid) for uid in raw[key] if isinstance(uid, (int, str)) and str(uid).isdigit())
    if user_id in current:
        current.discard(user_id)
        raw[key] = sorted(current)
        _save_raw(raw)
        return False  # 이제 지급받음
    else:
        current.add(user_id)
        raw[key] = sorted(current)
        _save_raw(raw)
        return True  # 이제 제외됨
