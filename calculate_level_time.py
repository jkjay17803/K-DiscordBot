# calculate_level_time.py - 각 레벨까지 걸리는 시간 계산

# config 값 직접 설정 (config.py에서 가져온 값)
BASE_EXP = 100
TIER_EXP_MULTIPLIERS = {
    0: 1.0,    # 1-9레벨
    1: 3.5,    # 10-19레벨
    2: 4.0,    # 20-29레벨
    3: 4.5,    # 30-39레벨
    4: 5.0,    # 40-49레벨
    5: 5.5,    # 50-59레벨
    6: 6.0,    # 60-69레벨
    7: 6.5,    # 70-79레벨
    8: 7.0,    # 80-89레벨
    9: 7.5,    # 90-99레벨
    10: 8.0,   # 100-109레벨
}
EXP_PER_MINUTE = 1

def get_tier_multiplier(tier: int) -> float:
    """티어에 해당하는 exp 배수 반환 (없으면 마지막 티어 값 사용)"""
    if tier in TIER_EXP_MULTIPLIERS:
        return TIER_EXP_MULTIPLIERS[tier]
    if TIER_EXP_MULTIPLIERS:
        max_tier = max(TIER_EXP_MULTIPLIERS.keys())
        return TIER_EXP_MULTIPLIERS[max_tier]
    return 1.0

def calculate_required_exp(level: int) -> int:
    """레벨업에 필요한 exp 계산"""
    if level < 1:
        return BASE_EXP
    
    tier = (level - 1) // 10
    tier_level = level - (tier * 10)
    
    if tier == 0:
        return BASE_EXP * tier_level
    else:
        prev_tier_last_exp = BASE_EXP * 9
        
        for t in range(1, tier):
            multiplier = get_tier_multiplier(t)
            prev_tier_base = prev_tier_last_exp * multiplier
            prev_tier_last_exp = prev_tier_base * 2
        
        multiplier = get_tier_multiplier(tier)
        tier_base_exp = prev_tier_last_exp * multiplier
        
        if tier_level == 1:
            return int(tier_base_exp)
        else:
            exp_increment = tier_base_exp / 9
            return int(tier_base_exp + (exp_increment * (tier_level - 1)))

def calculate_total_exp_to_level(target_level: int) -> int:
    """특정 레벨까지 필요한 총 exp 계산"""
    total_exp = 0
    for level in range(1, target_level + 1):
        total_exp += calculate_required_exp(level)
    return total_exp

def format_time(minutes: float) -> str:
    """분을 읽기 쉬운 형식으로 변환"""
    if minutes < 60:
        return f"{minutes:.1f}분"
    elif minutes < 1440:  # 24시간
        hours = minutes / 60
        return f"{hours:.1f}시간 ({minutes:.0f}분)"
    else:
        days = minutes / 1440
        hours = (minutes % 1440) / 60
        return f"{days:.1f}일 ({hours:.1f}시간)"

# 계산할 레벨들
target_levels = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

print("=" * 60)
print(f"레벨별 도달 시간 계산 (EXP_PER_MINUTE = {EXP_PER_MINUTE})")
print("=" * 60)
print(f"{'레벨':<8} {'필요 EXP':<15} {'시간 (분)':<15} {'시간 (읽기 쉬운 형식)':<20}")
print("-" * 60)

for level in target_levels:
    total_exp = calculate_total_exp_to_level(level)
    minutes = total_exp / EXP_PER_MINUTE
    time_str = format_time(minutes)
    
    print(f"{level:<8} {total_exp:<15,} {minutes:<15.1f} {time_str:<20}")

print("=" * 60)

