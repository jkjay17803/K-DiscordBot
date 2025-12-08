# config.py - 설정 파일

# Exp 획득 설정
EXP_PER_MINUTE = 1  # 1분당 1 exp

# 레벨업 설정
BASE_EXP = 100  # 기본 필요 exp
TIER_MULTIPLIER = 3.5  # 10의 단위 변경 시 배수 (3-4배 중간값)
POINTS_PER_LEVEL = 10  # 레벨업 시 포인트

# 닉네임 설정
NICKNAME_FORMAT = "[Lv.{level}] {original_nickname}"  # 레벨 표시 형식
NICKNAME_REFRESH_INTERVAL = 3600  # 1시간 (초 단위)

# 음성채널 체크 주기
VOICE_CHECK_INTERVAL = 60  # 1분마다 exp 체크 (초 단위)

# 명령어 제한 채널
RANK_COMMAND_CHANNEL_ID = 1447457558762622976  # None이면 모든 채널에서 사용 가능, 채널 ID를 입력하면 해당 채널에서만 사용 가능

