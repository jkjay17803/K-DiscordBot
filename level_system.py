# level_system.py - 레벨 시스템 로직

import math
from config import BASE_EXP, TIER_MULTIPLIER, POINTS_PER_LEVEL
from database import (
    get_or_create_user, update_user_exp, update_user_level,
    update_user_points
)


def calculate_required_exp(level: int) -> int:
    """
    레벨업에 필요한 exp 계산
    레벨의 10의 단위가 바뀔 때마다 필요 exp가 3-4배 증가
    """
    if level < 1:
        return BASE_EXP
    
    # 현재 레벨이 속한 티어 계산 (0티어: 1-9, 1티어: 10-19, ...)
    tier = (level - 1) // 10
    tier_level = level - (tier * 10)  # 티어 내에서의 레벨 (1-10)
    
    if tier == 0:
        # 1-9레벨: 기본 exp
        return BASE_EXP * tier_level
    else:
        # 10레벨 이상: 이전 티어의 마지막 exp를 기준으로 배수 적용
        prev_tier_last_exp = BASE_EXP * 9  # 9레벨까지의 exp
        
        # 각 티어마다 배수 적용
        tier_base_exp = prev_tier_last_exp * (TIER_MULTIPLIER ** tier)
        
        # 티어 내에서의 exp 계산
        if tier_level == 1:
            # 티어의 첫 레벨 (10, 20, 30, ...)
            return int(tier_base_exp)
        else:
            # 티어 내에서 점진적 증가
            exp_increment = tier_base_exp / 9  # 티어 내 9단계로 나눔
            return int(tier_base_exp + (exp_increment * (tier_level - 1)))


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
    new_total_exp = current_total_exp #+ exp_to_add
    
    # 새로운 레벨과 exp 계산
    new_level, new_exp = calculate_level_from_total_exp(new_total_exp)
    
    # 레벨업 체크
    leveled_up = new_level > current_level
    points_earned = 0
    
    if leveled_up:
        # 레벨업한 만큼 포인트 지급
        levels_gained = new_level - current_level
        points_earned = levels_gained * POINTS_PER_LEVEL
        new_points = current_points + points_earned
        
        await update_user_level(user_id, guild_id, new_level, new_exp, new_points)
    else:
        # exp만 업데이트
        await update_user_exp(user_id, guild_id, new_exp, new_total_exp)
        new_points = current_points
    
    return {
        'leveled_up': leveled_up,
        'new_level': new_level,
        'new_exp': new_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'required_exp': calculate_required_exp(new_level)
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

