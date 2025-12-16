# level_system.py - 레벨 시스템 로직

from config import EXP_PER_MINUTE, LEVEL_RANGES
from database import (
    get_or_create_user, update_user_exp, update_user_level,
)


def get_level_range(level: int) -> tuple:
    """
    레벨에 해당하는 구간 정보 반환
    Returns: (레벨업_시간_분, 레벨업_포인트) 또는 None
    """
    for (start, end), (minutes, points) in LEVEL_RANGES.items():
        if start <= level <= end:
            return (minutes, points)
    
    # 설정에 없는 레벨은 마지막 구간의 값 사용
    if LEVEL_RANGES:
        last_range = max(LEVEL_RANGES.keys(), key=lambda x: x[1])
        return LEVEL_RANGES[last_range]
    
    # 기본값
    return (10, 10)


def calculate_required_exp(level: int) -> int:
    """
    레벨업에 필요한 exp 계산
    레벨업 시간(분) * EXP_PER_MINUTE
    """
    if level < 1:
        level = 1
    
    minutes, _ = get_level_range(level)
    return int(minutes * EXP_PER_MINUTE)


def get_points_for_level(level: int) -> int:
    """레벨에 해당하는 레벨업 시 지급되는 포인트 반환"""
    _, points = get_level_range(level)
    return points


def calculate_level_from_total_exp(total_exp: int) -> tuple[int, int]:
    """
    총 exp로부터 현재 레벨과 남은 exp 계산
    Returns: (level, current_exp)
    """
    if total_exp < 0:
        return (1, 0)
    
    level = 1
    exp_needed = 0
    
    while True:
        required = calculate_required_exp(level)
        if exp_needed + required > total_exp:
            current_exp = total_exp - exp_needed
            return (level, current_exp)
        exp_needed += required
        level += 1
        
        # 무한 루프 방지 (레벨 1000 이상은 계산하지 않음)
        if level > 1000:
            return (1000, total_exp - exp_needed)


async def add_exp(user_id: int, guild_id: int, exp_to_add: int) -> dict:
    """
    사용자에게 exp 추가
    Returns: {
        'leveled_up': bool,
        'new_level': int,
        'new_exp': int,
        'points_earned': int,
        'new_points': int
    }
    """
    user = await get_or_create_user(user_id, guild_id)
    
    current_level = user['level']
    current_exp = user['exp']
    current_total_exp = user['total_exp']
    current_points = user['points']
    
    # 총 exp에 추가
    new_total_exp = current_total_exp + exp_to_add
    
    # 새로운 레벨과 exp 계산
    new_level, new_exp = calculate_level_from_total_exp(new_total_exp)
    
    # 레벨업 체크
    leveled_up = new_level > current_level
    points_earned = 0
    
    if leveled_up:
        # 레벨업한 만큼 포인트 지급 (각 레벨마다 티어별 포인트 적용)
        levels_gained = new_level - current_level
        points_earned = 0
        
        # 각 레벨업마다 해당 레벨의 티어에 맞는 포인트 지급
        for level in range(current_level + 1, new_level + 1):
            points_earned += get_points_for_level(level)
        
        new_points = current_points + points_earned
        
        await update_user_level(user_id, guild_id, new_level, new_exp, new_points, new_total_exp)
    else:
        # exp만 업데이트
        await update_user_exp(user_id, guild_id, new_exp, new_total_exp)
        new_points = current_points
    
    return {
        'leveled_up': leveled_up,
        'old_level': current_level,
        'new_level': new_level,
        'new_exp': new_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'required_exp': calculate_required_exp(new_level)
    }


async def set_level(user_id: int, guild_id: int, target_level: int) -> dict:
    """
    사용자의 레벨을 직접 설정
    Returns: {
        'old_level': int,
        'new_level': int,
        'new_exp': int,
        'points_earned': int,
        'new_points': int
    }
    """
    if target_level < 1:
        target_level = 1
    
    user = await get_or_create_user(user_id, guild_id)
    
    old_level = user['level']
    current_points = user['points']
    
    # 레벨이 같으면 변경 없음
    if old_level == target_level:
        return {
            'old_level': old_level,
            'new_level': target_level,
            'new_exp': 0,
            'points_earned': 0,
            'new_points': current_points,
            'required_exp': calculate_required_exp(target_level)
        }
    
    # 목표 레벨까지 필요한 총 exp 계산
    total_exp_needed = 0
    for level in range(1, target_level):
        total_exp_needed += calculate_required_exp(level)
    
    # 목표 레벨의 현재 exp는 0으로 설정
    new_exp = 0
    new_total_exp = total_exp_needed
    
    # 레벨업한 만큼 포인트 지급
    points_earned = 0
    if target_level > old_level:
        # 레벨업한 레벨들에 대한 포인트 지급
        for level in range(old_level + 1, target_level + 1):
            points_earned += get_points_for_level(level)
    else:
        # 레벨 다운인 경우 포인트 차감 (레벨 다운한 레벨들의 포인트 회수)
        for level in range(target_level + 1, old_level + 1):
            points_earned -= get_points_for_level(level)
    
    new_points = current_points + points_earned
    if new_points < 0:
        new_points = 0
    
    # 데이터베이스 업데이트
    await update_user_level(user_id, guild_id, target_level, new_exp, new_points, new_total_exp)
    
    return {
        'old_level': old_level,
        'new_level': target_level,
        'new_exp': new_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'required_exp': calculate_required_exp(target_level)
    }


async def get_user_level_info(user_id: int, guild_id: int) -> dict:
    """사용자의 레벨 정보 조회"""
    user = await get_or_create_user(user_id, guild_id)
    
    current_level = user['level']
    current_exp = user['exp']
    required_exp = calculate_required_exp(current_level)
    
    return {
        'level': current_level,
        'exp': current_exp,
        'required_exp': required_exp,
        'points': user['points'],
        'total_exp': user['total_exp']
    }

