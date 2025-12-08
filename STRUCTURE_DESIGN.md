# K 봇 구조 설계

## 📁 프로젝트 구조

```
K/
├── K.py                          # 메인 봇 파일
├── config.py                     # 설정 파일 (레벨업 규칙, exp 획득량 등)
├── database.py                   # 데이터베이스 관리 (SQLite)
├── level_system.py               # 레벨/포인트 시스템 로직
├── voice_monitor.py              # 음성채널 모니터링 및 exp 획득
├── nickname_manager.py           # 닉네임 레벨 표시 관리
├── commands/
│   ├── __init__.py
│   ├── level_command.py          # !레벨 명령어
│   └── rank_command.py           # !순위 명령어
├── utils/
│   ├── __init__.py
│   └── helpers.py                # 유틸리티 함수들
└── message_with_channel_id.py    # 기존 기능
```

## 🗄️ 데이터베이스 구조 (SQLite)

### users 테이블
```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    total_exp INTEGER DEFAULT 0,
    last_voice_join TIMESTAMP,
    last_nickname_update TIMESTAMP,
    UNIQUE(user_id, guild_id)
)
```

### voice_sessions 테이블 (세션 추적용)
```sql
CREATE TABLE voice_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    join_time TIMESTAMP NOT NULL,
    leave_time TIMESTAMP,
    exp_earned INTEGER DEFAULT 0
)
```

## 📦 모듈별 역할

### 1. config.py
- 레벨업 규칙 설정
- exp 획득 속도 (예: 1분당 1 exp)
- 레벨업 시 포인트 보상
- 10의 단위 변경 시 exp 배수 (3-4배)
- 닉네임 새로고침 주기 (1시간)

### 2. database.py
- 데이터베이스 초기화 및 연결 관리
- 사용자 데이터 CRUD 작업
- 음성 세션 기록
- 트랜잭션 관리

### 3. level_system.py
- 레벨 계산 로직
- 필요 exp 계산 (레벨의 10의 단위에 따라)
- 레벨업 처리
- 포인트 지급 계산
- exp 추가/차감

### 4. voice_monitor.py
- `on_voice_state_update` 이벤트 처리
- 음성채널 입장/퇴장 감지
- 백그라운드 작업으로 exp 누적
- 음성채널에 있는 동안 주기적으로 exp 추가

### 5. nickname_manager.py
- 닉네임에 레벨 표시 추가/제거
- 레벨업 시 즉시 닉네임 업데이트
- 1시간마다 모든 사용자 닉네임 새로고침
- 닉네임 변경 권한 확인

### 6. commands/level_command.py
- `!레벨` 명령어 구현
- 현재 레벨, 포인트, exp, 필요 exp 표시
- 이쁜 임베드 메시지로 표시

### 7. commands/rank_command.py
- `!순위` 명령어 구현
- 포인트/레벨 기준 순위 표시
- 상위 10명 또는 자신의 순위 표시

## 🔄 주요 플로우

### Exp 획득 플로우
1. 사용자가 음성채널 입장 → `voice_monitor.py` 감지
2. 백그라운드 작업 시작 (1분마다 exp 추가)
3. `level_system.py`의 `add_exp()` 호출
4. 레벨업 체크 → 레벨업 시:
   - 포인트 지급
   - `nickname_manager.py`로 닉네임 즉시 업데이트
5. 사용자가 음성채널 퇴장 → 백그라운드 작업 중지

### 닉네임 새로고침 플로우
1. 백그라운드 작업 (1시간마다)
2. 모든 서버의 모든 사용자 순회
3. 데이터베이스에서 레벨 조회
4. 현재 닉네임 확인 → 레벨 표시가 없거나 다르면 업데이트

### 레벨업 규칙 예시
```
레벨 1-9:    필요 exp = 100 * level
레벨 10-19:  필요 exp = 300 * (level - 9) + 900
레벨 20-29:  필요 exp = 1200 * (level - 19) + 3900
레벨 30-39:  필요 exp = 4800 * (level - 29) + 15900
...
```

## ⚙️ 설정 예시 (config.py)

```python
# Exp 획득 설정
EXP_PER_MINUTE = 1  # 1분당 1 exp

# 레벨업 설정
BASE_EXP = 100
TIER_MULTIPLIER = 3.5  # 10의 단위 변경 시 배수
POINTS_PER_LEVEL = 10  # 레벨업 시 포인트

# 닉네임 설정
NICKNAME_FORMAT = "[Lv.{level}] {original_nickname}"
NICKNAME_REFRESH_INTERVAL = 3600  # 1시간 (초 단위)
```

## 🔧 구현 순서 제안

1. **데이터베이스 구조** (`database.py`)
   - 테이블 생성
   - 기본 CRUD 함수

2. **레벨 시스템 로직** (`level_system.py`)
   - 레벨 계산 함수
   - exp 추가 함수
   - 레벨업 체크

3. **음성 모니터링** (`voice_monitor.py`)
   - 입장/퇴장 감지
   - 백그라운드 exp 누적

4. **닉네임 관리** (`nickname_manager.py`)
   - 레벨 표시 추가/제거
   - 자동 새로고침

5. **명령어 구현** (`commands/`)
   - !레벨
   - !순위

6. **통합 및 테스트**

## 📝 주의사항

1. **권한 관리**: 봇이 닉네임을 변경할 수 있는 권한 필요
2. **에러 처리**: 닉네임 변경 실패 시 로그만 남기고 계속 진행
3. **성능**: 대량 사용자 처리 시 비동기 작업 최적화
4. **데이터 백업**: 정기적인 데이터베이스 백업 고려
5. **레벨 표시 형식**: 사용자가 닉네임을 수정해도 1시간마다 복구

