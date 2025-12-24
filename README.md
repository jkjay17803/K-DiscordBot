# K 봇 (K Bot) - Discord 레벨 & 마켓 시스템

Discord 서버를 위한 레벨 시스템과 티켓 마켓 기능을 제공하는 봇입니다.

## 📋 목차

- [주요 기능](#주요-기능)
- [설치 및 설정](#설치-및-설정)
- [명령어 목록](#명령어-목록)
- [프로젝트 구조](#프로젝트-구조)
- [설정 파일](#설정-파일)
- [데이터베이스 구조](#데이터베이스-구조)
- [마켓 시스템](#마켓-시스템)
- [로그 시스템](#로그-시스템)

## 🎯 주요 기능

### 1. 레벨 시스템
- 음성 채널 활동을 통한 경험치(EXP) 획득
- 레벨업 시 포인트 지급
- 닉네임에 레벨 자동 표시 (`[Lv.XX] 닉네임`)
- 레벨 및 경험치 조회 기능

### 2. 포인트 시스템
- 레벨업 시 포인트 획득
- 포인트를 사용한 티켓 구매
- 포인트 및 레벨 순위 확인

### 3. 마켓 시스템
- 티켓 기반 물품 판매
- 사용자별 구매 제한 설정
- 구매 내역 조회
- 티켓 추첨 시스템

### 4. 관리자 기능
- 경험치/레벨/포인트 직접 조정
- 메시지 삭제 기능
- 모든 관리자 작업 로그 기록

## 🚀 설치 및 설정

### 1. 필수 요구사항
- Python 3.8 이상
- Discord Bot Token

### 2. 설치 방법

```bash
# 저장소 클론
git clone <repository-url>
cd K

# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```
DISCORD_TOKEN=your_bot_token_here
```

### 4. 설정 파일 수정

`config.py` 파일에서 다음 항목들을 설정하세요:

- `VOICE_CHANNEL_EXP`: 음성 채널별 EXP 지급 설정
- `LEVEL_RANGES`: 레벨업 구간별 설정
- `RANK_COMMAND_CHANNEL_ID`: 순위 명령어 제한 채널
- `MARKET_COMMAND_CHANNEL_ID`: 마켓 명령어 제한 채널
- `LOG_CHANNEL_ID_JK`: JK 명령어 로그 채널
- `LOG_CHANNEL_ID_LEVEL`: 레벨업 로그 채널
- `LOG_CHANNEL_ID_MARKET`: 마켓 로그 채널

### 5. 봇 실행

```bash
python K.py
```

## 📝 명령어 목록

### 일반 사용자 명령어

#### `!레벨 [@사용자]`
- 자신 또는 다른 사용자의 레벨 정보를 표시합니다.
- 레벨, 경험치 진행률, 포인트, 총 경험치를 보여줍니다.
- **제한**: `RANK_COMMAND_CHANNEL_ID` 채널에서만 사용 가능

#### `!순위 [포인트|레벨]`
- 서버의 포인트 또는 레벨 순위를 표시합니다.
- 상위 10명과 자신의 순위를 보여줍니다.
- **제한**: `RANK_COMMAND_CHANNEL_ID` 채널에서만 사용 가능

#### `!마켓`
- 현재 판매 중인 모든 물품 목록을 표시합니다.
- 물품 코드, 티켓 가격, 뽑는 인원, 구매된 티켓 수 등을 보여줍니다.
- **제한**: `MARKET_COMMAND_CHANNEL_ID` 채널에서만 사용 가능

#### `!구매 [물품코드]`
- 티켓을 구매합니다.
- 구매 확인 버튼을 통해 안전하게 구매할 수 있습니다.
- 포인트 부족 시 구매 불가
- 최대 구매 수량 초과 시 구매 불가
- **제한**: `MARKET_COMMAND_CHANNEL_ID` 채널에서만 사용 가능

#### `!티켓목록`
- 자신이 구매한 티켓 목록을 확인합니다.
- 물품별 보유 티켓 수를 표시합니다.
- **제한**: `MARKET_COMMAND_CHANNEL_ID` 채널에서만 사용 가능

### 관리자 명령어 (JK 역할 필요)

#### `!jk경험치 add [사용자ID|i] [exp수치]`
- 사용자에게 경험치를 추가합니다.
- `i`를 입력하면 자신에게 적용됩니다.
- 레벨업 시 자동으로 포인트 지급 및 로그 기록

#### `!jk경험치 set [사용자ID|i] [exp수치]`
- 사용자의 현재 레벨 경험치 진행률을 설정합니다.
- 총 경험치가 자동으로 조정됩니다.

#### `!jk레벨 add [사용자ID|i] [레벨수]`
- 사용자의 레벨을 추가합니다.
- 포인트는 변하지 않습니다.

#### `!jk레벨 set [사용자ID|i] [레벨]`
- 사용자의 레벨을 설정합니다.
- 포인트는 변하지 않습니다.

#### `!jk포인트 add [사용자ID|i] [포인트수]`
- 사용자에게 포인트를 추가합니다.

#### `!jk포인트 set [사용자ID|i] [포인트]`
- 사용자의 포인트를 설정합니다.

#### `!jk클리어 [줄 개수]`
- 채널에서 지정한 개수만큼 메시지를 삭제합니다.
- 최대 100개까지 삭제 가능

## 📁 프로젝트 구조

```
K/
├── K.py                          # 메인 봇 파일
├── config.py                     # 설정 파일
├── database.py                   # 데이터베이스 관리 (SQLite)
├── level_system.py               # 레벨/포인트 시스템 로직
├── voice_monitor.py              # 음성채널 모니터링 및 EXP 획득
├── nickname_manager.py           # 닉네임 레벨 표시 관리
├── market_manager.py             # 마켓 파일 관리
├── logger.py                     # 로그 시스템
├── market.py                     # 마켓 관리 스크립트 (수동 실행)
├── message_with_channel_id.py    # 메시지 전송 기능
├── commands/
│   ├── __init__.py
│   ├── level_command.py          # !레벨 명령어
│   ├── rank_command.py          # !순위 명령어
│   ├── admin_command.py         # !jk 명령어들
│   └── market_command.py        # !마켓, !구매, !티켓목록 명령어
├── market/                       # 마켓 파일 저장 폴더 (gitignore)
│   └── YY_MM_market.txt          # 마켓 파일 형식
├── requirements.txt              # Python 패키지 목록
├── .env                          # 환경 변수 (gitignore)
└── k_bot.db                      # SQLite 데이터베이스 (gitignore)
```

## ⚙️ 설정 파일

### config.py 주요 설정

#### 음성 채널 EXP 설정
```python
VOICE_CHANNEL_EXP = {
    1439835006410293379: (1, 1),  # 채널ID: (지급주기_분, 지급경험치)
}
```

#### 레벨업 설정
```python
LEVEL_RANGES = {
    (1, 10): (10, 10),      # 레벨구간: (레벨업_시간_분, 레벨업_포인트)
    (11, 20): (11, 12),
    # ...
}
```

#### 채널 제한 설정
```python
RANK_COMMAND_CHANNEL_ID = 1447457558762622976      # 순위 명령어 채널
MARKET_COMMAND_CHANNEL_ID = 1453344981141033018    # 마켓 명령어 채널
```

#### 로그 채널 설정
```python
LOG_CHANNEL_ID_JK = 1449333459037192192      # JK 명령어 로그
LOG_CHANNEL_ID_LEVEL = 1453357356363677739    # 레벨업 로그
LOG_CHANNEL_ID_MARKET = 1453357389418991667   # 마켓 로그
```

## 🗄️ 데이터베이스 구조

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

### voice_sessions 테이블
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

## 🛒 마켓 시스템

### 마켓 파일 형식

마켓 파일은 `market/` 폴더에 `YY_MM_market.txt` 형식으로 저장됩니다.

```
# [물품 이름] : [물품 코드]
[뽑는 인원 수] : [구매 가능 수]
p : [티켓 당 가격]
[티켓 발행 수]
@구매자 이름
@구매자 이름
...
```

**예시:**
```
# 햄버거 상품권 : ASAV1231
1 : 2
p : 4000
0
@홍길동
@김철수
```

### 마켓 파일 설명

- **물품 이름**: 판매할 물품의 이름
- **물품 코드**: 구매 시 사용하는 고유 코드
- **뽑는 인원 수**: 구매된 티켓 중 당첨될 인원 수
- **구매 가능 수**: 한 사람당 최대 구매 가능한 티켓 수
- **티켓 당 가격**: 티켓 하나의 가격 (포인트)
- **티켓 발행 수**: 현재까지 판매된 티켓 수
- **구매자 목록**: 티켓을 구매한 사용자들의 이름

### 마켓 관리 스크립트

`market.py`를 실행하여 구매 내역을 확인할 수 있습니다:

```bash
python market.py
```

- `0`: 종료
- `1`: 누가 어떤 물품을 얼마나 샀는지 표시

## 📊 로그 시스템

모든 중요한 작업은 별도의 로그 채널에 기록됩니다:

### JK 명령어 로그
- 모든 `!jk` 명령어 실행 내역
- 실행자, 대상 사용자, 변경 내용 등

### 레벨업 로그
- 사용자 레벨업 시 자동 기록
- 레벨 변화, 획득 포인트, 현재 포인트 등

### 마켓 로그
- 티켓 구매 내역
- 구매자, 물품 정보, 가격, 보유 티켓 수 등

## 🔧 주요 기능 상세

### 경험치 획득 시스템

1. 사용자가 음성 채널에 입장
2. 설정된 주기마다 경험치 자동 지급
3. 레벨업 조건 충족 시 자동 레벨업
4. 레벨업 시 포인트 지급 및 닉네임 업데이트

### 닉네임 관리

- 레벨업 시 즉시 닉네임 업데이트
- 1시간마다 모든 사용자 닉네임 자동 새로고침
- 닉네임 형식: `[Lv.{level}] {original_nickname}`

### 티켓 구매 프로세스

1. `!마켓`으로 물품 확인
2. `!구매 [물품코드]` 입력
3. 구매 확인 버튼 클릭
4. 포인트 차감 및 티켓 발행
5. 로그 채널에 기록

## 📌 주의사항

1. **권한 관리**: 봇이 닉네임을 변경할 수 있는 권한이 필요합니다.
2. **채널 제한**: 일부 명령어는 특정 채널에서만 사용 가능합니다.
3. **데이터 백업**: 정기적으로 데이터베이스 백업을 권장합니다.
4. **마켓 파일**: `market/` 폴더는 `.gitignore`에 포함되어 있습니다.

## 📄 라이선스

이 프로젝트는 개인 사용을 위한 것입니다.

## 👤 개발자

JK

---

**버전**: Beta 1.0
