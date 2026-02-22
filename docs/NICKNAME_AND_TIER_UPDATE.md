# 별명(닉네임)과 칭호(티어 역할) 업데이트 시점·방식

## 1. 별명(닉네임) 업데이트

### 표시 형식
- **일반 사용자**: `[Lv.{레벨}] {원래 닉네임}` (config: `NICKNAME_FORMAT`)
- **JK 역할 사용자**: `[ ✬ ] {원래 닉네임}` (레벨 표시 없음, 운영자 아이콘만)

### 언제·어떻게 갱신되는지

| 시점 | 방식 | 파일/위치 |
|------|------|------------|
| **봇 기동 시** | DB에 있는 모든 유저에 대해 닉네임·티어 일괄 갱신 | `K.py` → `initial_nickname_update(k)` |
| **서버 입장 (on_member_join)** | 신규: 레벨 1로 닉네임·티어 설정. 재입장: DB 레벨로 닉네임·티어 동기화 | `K.py` → `update_user_nickname`, `update_tier_role` |
| **음성 채널 입장** | DB 레벨 기준으로 닉네임·티어 동기화 (레벨업 반영용) | `voice_monitor.py` → `sync_level_display(member)` |
| **채팅 (on_message)** | DB 레벨 기준으로 닉네임·티어 동기화, **5분당 1회** 쓰로틀 | `message_with_channel_id.py` → `sync_level_display(message.author)` |
| **JK 역할 부여** | Discord에서 JK 역할이 추가된 순간, 별명에 `[ ✬ ]` 적용 | `nickname_manager.py` → `on_member_update` (역할 변경 감지) |
| **닉네임 수동 변경** | 사용자가 닉네임을 바꾸면, DB 레벨에 맞춰 `[Lv.N]` 또는 JK 아이콘 복원 | `nickname_manager.py` → `on_member_update` → `check_and_restore_nickname` |
| **JK 명령어로 레벨/EXP 변경** | `/jk exp add`, `/jk level set` 등 실행 시 대상 유저 닉네임·티어 즉시 갱신 | `slash_commands.py`, `admin_command.py` → `update_user_nickname`, `update_tier_role` |
| **/jk reboot** | 모든 유저에 대해 티어 역할만 일괄 동기화 (닉네임은 건드리지 않음) | `slash_commands.py` → `update_tier_role` |

### 음성 채널 레벨업 시
- **레벨업 당시**: 닉네임·티어는 **바로 수정하지 않음** (로그만 전송).
- **이후**: 해당 유저가 **음성 입장**하거나 **채팅**할 때 `sync_level_display`로 DB 레벨에 맞춰 별명·칭호가 갱신됨.

### 1시간 주기 새로고침
- `refresh_all_nicknames(bot)` / `setup_nickname_refresh(bot)` 는 **현재 K.py에서 호출되지 않음**.
- 따라서 **1시간마다 자동으로 전체 닉네임 새로고침**하는 동작은 **실행되지 않는 상태**임.

---

## 2. 칭호(티어 역할) 업데이트

### 표시
- 레벨 구간별 티어 역할 (브론즈, 실버, 골드 등) → `tier_roles.txt` / config `get_tier_roles()` 기준.
- `update_tier_role(member, level)` 이 레벨에 맞는 티어 역할을 부여/제거.

### 언제·어떻게 갱신되는지

| 시점 | 방식 | 파일/위치 |
|------|------|------------|
| **봇 기동 시** | DB 유저 전체에 대해 티어 역할 일괄 갱신 | `K.py` → `initial_tier_role_update(k)` |
| **서버 입장** | 신규: 브론즈 등 레벨 1 티어. 재입장: DB 레벨에 맞는 티어로 동기화 | `K.py` → `update_tier_role` |
| **음성 입장** | DB 레벨에 맞춰 티어 동기화 | `voice_monitor.py` → `sync_level_display` → `update_tier_role` |
| **채팅** | DB 레벨에 맞춰 티어 동기화 (5분당 1회) | `message_with_channel_id.py` → `sync_level_display` → `update_tier_role` |
| **JK 명령어로 레벨/EXP 변경** | 대상 유저 티어 즉시 갱신 | `slash_commands.py`, `admin_command.py` → `update_tier_role` |
| **/jk reboot** | 모든 유저 티어만 일괄 동기화 | `slash_commands.py` → `update_tier_role` |

---

## 3. 요약

- **별명**: 봇 기동·입장·음성 입장·채팅(5분 쿨)·JK 역할 부여·닉네임 수동 변경·JK 명령어 실행 시 갱신. 음성 레벨업은 당시에는 안 바꾸고, 다음 상호작용 시 동기화.
- **칭호**: 봇 기동·입장·음성 입장·채팅(5분 쿨)·JK 명령어·/jk reboot 시 갱신.
- **1시간 주기 전체 닉네임 새로고침**은 코드에는 있으나, 현재는 **호출되지 않아 동작하지 않음**.
