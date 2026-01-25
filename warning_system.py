# warning_system.py - 경고 시스템

import discord
from datetime import datetime, timedelta
from database import (
    add_warning, get_active_warning_count, get_all_warnings,
    remove_warnings
)
from level_system import add_points


async def issue_warning(user_id: int, guild_id: int, reason: str, issued_by: int, warning_count: int = 1) -> dict:
    """
    경고 부여
    Returns: {
        'warning_count': int,  # 부여된 경고 수
        'total_warnings': int,  # 총 경고 수
        'points_deducted': int,  # 차감된 포인트
        'new_points': int  # 차감 후 포인트
    }
    """
    # 경고 추가
    await add_warning(user_id, guild_id, reason, issued_by, warning_count)
    
    # 총 경고 수 조회
    total_warnings = await get_active_warning_count(user_id, guild_id)
    
    # 포인트 차감 (경고 1개당 100포인트)
    points_deducted = warning_count * 100
    
    # 포인트 차감 (마이너스도 가능)
    result = await add_points(user_id, guild_id, -points_deducted, allow_negative=True)
    new_points = result['new_points']
    
    return {
        'warning_count': warning_count,
        'total_warnings': total_warnings,
        'points_deducted': points_deducted,
        'new_points': new_points
    }


async def remove_warning(user_id: int, guild_id: int, count: int) -> dict:
    """
    경고 해제
    Returns: {
        'removed_count': int,  # 해제된 경고 수
        'total_warnings': int,  # 해제 후 총 경고 수
        'points_restored': int,  # 복구된 포인트
        'new_points': int  # 복구 후 포인트
    }
    """
    # 현재 경고 수 확인
    current_warnings = await get_active_warning_count(user_id, guild_id)
    
    # 해제할 수 있는 경고 수 제한
    actual_remove_count = min(count, current_warnings)
    
    if actual_remove_count == 0:
        return {
            'removed_count': 0,
            'total_warnings': current_warnings,
            'points_restored': 0,
            'new_points': 0
        }
    
    # 경고 삭제
    removed = await remove_warnings(user_id, guild_id, actual_remove_count)
    
    # 총 경고 수 조회
    total_warnings = await get_active_warning_count(user_id, guild_id)
    
    # 포인트 복구 (경고 1개당 100포인트)
    points_restored = removed * 100
    
    # 포인트 복구
    result = await add_points(user_id, guild_id, points_restored, allow_negative=False)
    new_points = result['new_points']
    
    return {
        'removed_count': removed,
        'total_warnings': total_warnings,
        'points_restored': points_restored,
        'new_points': new_points
    }


async def check_warning_restrictions(user_id: int, guild_id: int) -> dict:
    """
    경고에 따른 제한 사항 확인
    Returns: {
        'can_send_messages': bool,  # 메시지 보내기 가능 여부
        'can_use_market': bool,  # 마켓 이용 가능 여부
        'can_use_voice': bool,  # 음성 채팅방 이용 가능 여부
        'should_ban': bool,  # 차단 여부
        'warning_count': int  # 현재 경고 수
    }
    """
    warning_count = await get_active_warning_count(user_id, guild_id)
    
    return {
        'can_send_messages': warning_count < 3,
        'can_use_market': warning_count < 5,
        'can_use_voice': warning_count < 7,
        'should_ban': warning_count >= 10,
        'warning_count': warning_count
    }

