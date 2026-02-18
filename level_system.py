# level_system.py - 레벨 시스템 로직

from config import EXP_PER_MINUTE, get_level_ranges
from database import (
    get_or_create_user, update_user_exp, update_user_level, update_user_points,
)


def get_level_range(level: int) -> tuple:
    """
    레벨에 해당하는 구간 정보 반환
    Returns: (레벨업_시간_분, 레벨업_포인트) 또는 None
    """
    level_ranges = get_level_ranges()  # 동적으로 로드
    
    for (start, end), (minutes, points) in level_ranges.items():
        if start <= level <= end:
            return (minutes, points)
    
    # 설정에 없는 레벨은 마지막 구간의 값 사용
    if level_ranges:
        last_range = max(level_ranges.keys(), key=lambda x: x[1])
        return level_ranges[last_range]
    
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


async def add_exp(user_id: int, guild_id: int, exp_to_add: int, use_transaction: bool = False) -> dict:
    """
    사용자에게 exp 추가
    Args:
        use_transaction: True면 트랜잭션 모드 (커밋하지 않음, 호출자가 커밋/롤백 처리)
    Returns: {
        'leveled_up': bool,
        'new_level': int,
        'new_exp': int,
        'points_earned': int,
        'new_points': int,
        'db': DB connection (use_transaction=True일 때만, commit/rollback/close 책임)
    }
    """
    from datetime import datetime
    from database import get_mysql_connection, get_or_create_user
    
    conn = None
    cursor = None
    
    if use_transaction:
        conn = await get_mysql_connection()
        cursor = conn.cursor()  # aiosqlite: cursor()는 동기

        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:26]
            await cursor.execute(
                "SELECT level, exp, points, total_exp FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            row = await cursor.fetchone()
            if row is None:
                await cursor.execute(
                    """INSERT INTO users 
                       (user_id, guild_id, level, exp, points, total_exp, last_nickname_update)
                       VALUES (?, ?, 1, 0, 0, 0, ?)""",
                    (user_id, guild_id, now_str)
                )
                user = {'level': 1, 'exp': 0, 'points': 0, 'total_exp': 0}
            else:
                user = {'level': row[0], 'exp': row[1], 'points': row[2], 'total_exp': row[3]}
        except Exception as e:
            await conn.rollback()
            await conn.close()
            raise e
    else:
        user = await get_or_create_user(user_id, guild_id)
    
    current_level = user['level']
    current_exp = user['exp']
    current_total_exp = user['total_exp']
    current_points = user['points']
    
    new_total_exp = current_total_exp + exp_to_add
    new_level, new_exp = calculate_level_from_total_exp(new_total_exp)
    leveled_up = new_level > current_level
    points_earned = 0
    
    if leveled_up:
        for level in range(current_level + 1, new_level + 1):
            points_earned += get_points_for_level(level)
        new_points = current_points + points_earned
        await update_user_level(user_id, guild_id, new_level, new_exp, new_points, new_total_exp, cursor=cursor)
    else:
        await update_user_exp(user_id, guild_id, new_exp, new_total_exp, cursor=cursor)
        new_points = current_points
    
    result = {
        'leveled_up': leveled_up,
        'old_level': current_level,
        'new_level': new_level,
        'new_exp': new_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'old_total_exp': current_total_exp,
        'new_total_exp': new_total_exp,
        'required_exp': calculate_required_exp(new_level)
    }
    
    if use_transaction:
        result['db'] = conn
    
    return result


async def set_level(user_id: int, guild_id: int, target_level: int, award_points: bool = False) -> dict:
    """
    사용자의 레벨을 직접 설정
    award_points: True면 낮은 레벨→높은 레벨일 때만, 현재 레벨+1 ~ 목표 레벨까지의 레벨업 포인트 지급
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
    old_total_exp = user['total_exp']
    current_points = user['points'] if user.get('points') is not None else 0
    
    # 레벨이 같으면 변경 없음
    if old_level == target_level:
        return {
            'old_level': old_level,
            'new_level': target_level,
            'new_exp': 0,
            'points_earned': 0,
            'new_points': current_points,
            'old_total_exp': old_total_exp,
            'new_total_exp': old_total_exp,
            'required_exp': calculate_required_exp(target_level)
        }
    
    # 목표 레벨까지 필요한 총 exp 계산
    total_exp_needed = 0
    for level in range(1, target_level):
        total_exp_needed += calculate_required_exp(level)
    
    # 목표 레벨의 현재 exp는 0으로 설정
    new_exp = 0
    new_total_exp = total_exp_needed
    
    # 포인트: 낮은→높은 레벨일 때만 (현재+1 ~ 목표 레벨) 구간 레벨업 포인트 지급, 높은→낮은 레벨은 지급 없음
    points_earned = 0
    if award_points and target_level > old_level:
        for level in range(old_level + 1, target_level + 1):
            points_earned += get_points_for_level(level)
    new_points = current_points + points_earned
    
    # 데이터베이스 업데이트
    await update_user_level(user_id, guild_id, target_level, new_exp, new_points, new_total_exp)
    
    return {
        'old_level': old_level,
        'new_level': target_level,
        'new_exp': new_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'old_total_exp': old_total_exp,
        'new_total_exp': new_total_exp,
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


async def set_current_exp(user_id: int, guild_id: int, target_exp: int) -> dict:
    """
    사용자의 현재 레벨의 경험치를 직접 설정 (경험치 진행률 변경)
    Returns: {
        'old_level': int,
        'new_level': int,
        'old_exp': int,
        'new_exp': int,
        'old_total_exp': int,
        'new_total_exp': int,
        'points_earned': int,
        'new_points': int
    }
    """
    if target_exp < 0:
        target_exp = 0
    
    user = await get_or_create_user(user_id, guild_id)
    
    old_level = user['level']
    old_exp = user['exp']
    old_total_exp = user['total_exp']
    current_points = user['points']
    
    # 현재 총 경험치에서 현재 경험치를 빼서 "현재 레벨까지의 총 경험치" 계산
    # (현재 레벨의 경험치를 제외한 총 경험치)
    total_exp_before_current_level = old_total_exp - old_exp
    
    # 새로운 총 경험치 = 현재 레벨까지의 총 경험치 + 설정할 경험치
    new_total_exp = total_exp_before_current_level + target_exp
    required_exp = calculate_required_exp(old_level)
    
    # 설정한 경험치가 필요 경험치를 넘으면 레벨업 처리
    if target_exp >= required_exp:
        # 레벨업 처리
        new_level, new_exp = calculate_level_from_total_exp(new_total_exp)
    else:
        # 레벨은 그대로, 경험치만 변경
        new_level = old_level
        new_exp = target_exp
    
    # 레벨 변화에 따른 포인트 계산
    points_earned = 0
    if new_level > old_level:
        # 레벨업한 레벨들에 대한 포인트 지급
        for level in range(old_level + 1, new_level + 1):
            points_earned += get_points_for_level(level)
    elif new_level < old_level:
        # 레벨 다운인 경우 포인트 차감 (이론적으로는 발생하지 않아야 함)
        for level in range(new_level + 1, old_level + 1):
            points_earned -= get_points_for_level(level)
    
    new_points = current_points + points_earned
    if new_points < 0:
        new_points = 0
    
    # 데이터베이스 업데이트
    await update_user_level(user_id, guild_id, new_level, new_exp, new_points, new_total_exp)
    
    return {
        'old_level': old_level,
        'new_level': new_level,
        'old_exp': old_exp,
        'new_exp': new_exp,
        'old_total_exp': old_total_exp,
        'new_total_exp': new_total_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'required_exp': calculate_required_exp(new_level)
    }


async def set_exp(user_id: int, guild_id: int, target_total_exp: int) -> dict:
    """
    사용자의 총 경험치를 직접 설정
    Returns: {
        'old_level': int,
        'new_level': int,
        'old_exp': int,
        'new_exp': int,
        'old_total_exp': int,
        'new_total_exp': int,
        'points_earned': int,
        'new_points': int
    }
    """
    if target_total_exp < 0:
        target_total_exp = 0
    
    user = await get_or_create_user(user_id, guild_id)
    
    old_level = user['level']
    old_exp = user['exp']
    old_total_exp = user['total_exp']
    current_points = user['points']
    
    # 새로운 레벨과 exp 계산
    new_level, new_exp = calculate_level_from_total_exp(target_total_exp)
    
    # 레벨 변화에 따른 포인트 계산
    points_earned = 0
    if new_level > old_level:
        # 레벨업한 레벨들에 대한 포인트 지급
        for level in range(old_level + 1, new_level + 1):
            points_earned += get_points_for_level(level)
    elif new_level < old_level:
        # 레벨 다운인 경우 포인트 차감
        for level in range(new_level + 1, old_level + 1):
            points_earned -= get_points_for_level(level)
    
    new_points = current_points + points_earned
    if new_points < 0:
        new_points = 0
    
    # 데이터베이스 업데이트
    await update_user_level(user_id, guild_id, new_level, new_exp, new_points, target_total_exp)
    
    return {
        'old_level': old_level,
        'new_level': new_level,
        'old_exp': old_exp,
        'new_exp': new_exp,
        'old_total_exp': old_total_exp,
        'new_total_exp': target_total_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'required_exp': calculate_required_exp(new_level)
    }


async def add_level(user_id: int, guild_id: int, levels_to_add: int) -> dict:
    """
    사용자의 레벨을 추가
    Returns: {
        'old_level': int,
        'new_level': int,
        'new_exp': int,
        'points_earned': int,
        'new_points': int
    }
    """
    user = await get_or_create_user(user_id, guild_id)
    
    old_level = user['level']
    old_total_exp = user['total_exp']
    current_points = user['points']
    
    new_level = old_level + levels_to_add
    if new_level < 1:
        new_level = 1
    
    # 목표 레벨까지 필요한 총 exp 계산
    total_exp_needed = 0
    for level in range(1, new_level):
        total_exp_needed += calculate_required_exp(level)
    
    # 목표 레벨의 현재 exp는 0으로 설정
    new_exp = 0
    new_total_exp = total_exp_needed
    
    # 레벨 변경 시 포인트는 변하지 않음
    points_earned = 0
    new_points = current_points
    
    # 데이터베이스 업데이트
    await update_user_level(user_id, guild_id, new_level, new_exp, new_points, new_total_exp)
    
    return {
        'old_level': old_level,
        'new_level': new_level,
        'new_exp': new_exp,
        'points_earned': points_earned,
        'new_points': new_points,
        'old_total_exp': old_total_exp,
        'new_total_exp': new_total_exp,
        'required_exp': calculate_required_exp(new_level)
    }


async def add_points(user_id: int, guild_id: int, points_to_add: int, allow_negative: bool = False) -> dict:
    """
    사용자에게 포인트 추가
    Args:
        allow_negative: True이면 마이너스 포인트 허용 (경고 시스템 등에서 사용)
    Returns: {
        'old_points': int,
        'new_points': int
    }
    """
    user = await get_or_create_user(user_id, guild_id)
    
    old_points = user['points']
    new_points = old_points + points_to_add
    
    if not allow_negative and new_points < 0:
        new_points = 0
    
    await update_user_points(user_id, guild_id, new_points)
    
    return {
        'old_points': old_points,
        'new_points': new_points
    }


async def set_points(user_id: int, guild_id: int, target_points: int) -> dict:
    """
    사용자의 포인트를 직접 설정
    Returns: {
        'old_points': int,
        'new_points': int
    }
    """
    if target_points < 0:
        target_points = 0
    
    user = await get_or_create_user(user_id, guild_id)
    
    old_points = user['points']
    
    await update_user_points(user_id, guild_id, target_points)
    
    return {
        'old_points': old_points,
        'new_points': target_points
    }
