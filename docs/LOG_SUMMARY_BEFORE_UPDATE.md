# K 디스코드 봇 로그 정리 (업데이트 적용 전)

**기간**: 2026-02-18 15:16 ~ 2026-02-22 12:19  
**환경**: 라즈베리파이 (geths-pi3), Python 3.11

---

## 1. 봇 기동 (2026-02-18 15:16:52)

| 항목 | 내용 |
|------|------|
| 로그인 | `JK-K#3294` |
| DB 초기화 | 완료 |
| 멤버 초기화 | 0명 생성, 24명 기존 |
| 음성 모니터 | 활성화 |
| 음성 세션 | 0명 (이미 접속 중인 사용자 없음) |
| 닉네임 일괄 갱신 | 24명 성공, 0명 실패 |
| 티어 역할 일괄 갱신 | 24명 성공, 0명 실패 |
| 닉네임 이벤트 핸들러 | 등록됨 (이벤트 기반) |
| 슬래시 명령어 | 글로벌 동기화 6개 |
| 상태 | `K 봇이 준비되었습니다!` |

---

## 2. Discord Gateway (세션 유지)

- **RESUMED**: 세션이 끊겼다가 다시 이어질 때마다 `Shard ID None has successfully RESUMED session ...` 로그 발생.
- **발생 시각 예**: 17:51, 19:13, 22:40, 23:20 (18일), 00:53, 03:43, 04:43, 06:16 … (19~22일에도 반복).
- 네트워크/재연결 시 정상 동작으로 기록된 내용.

---

## 3. 음성 채널 입·퇴장 (VoiceMonitor)

### 3-1. EXP 설정이 있는 채널

| 채널명 | 서버 | EXP 설정 |
|--------|------|----------|
| 🎙️대화 | JK-코딩허브 | 5분마다 1 exp |
| 📝-공부방-👥✅ | JK-코딩허브 | 1분마다 1 exp |

### 3-2. 입·퇴장 요약

| 사용자 | 입장 채널 | 퇴장 시 earned |
|--------|-----------|----------------|
| nayejun9136 | 🎙️대화, 📝-공부방-👥✅ | **항상 0 exp** |
| jk_17803 | 🎙️대화 | 0 exp |
| jk_live_92732 | 🎙️대화, 📝-공부방-👥✅ | 0 exp |

- 퇴장 로그에 `earned 0 exp`만 찍힌 이유: 아래 4번 오류로 실제 지급이 되지 않음.

---

## 4. 오류: EXP 누적 실패 (DB 미반영 원인)

**에러 메시지**  
`'Result' object has no attribute 'execute'`

**발생 위치**  
`voice_monitor.py` → exp accumulation (약 280번째 줄 근처)

**추가 경고**  
`RuntimeWarning: coroutine 'Connection.cursor' was never awaited`

**의미**

- `level_system.add_exp(..., use_transaction=True)`에서 aiosqlite 연결을 쓰는데,
  - `conn.cursor()`를 `await`하지 않아서 커서 대신 코루틴/Result 객체가 넘어감.
  - 또는 aiosqlite 버전에 따라 `conn.execute()` 반환값(Result)에 `.execute`를 호출하는 코드가 섞여 있음.
- 그 결과 `update_user_exp(..., cursor=cursor)` 등에서 `cursor.execute()` 호출 시 `'Result' object has no attribute 'execute'` 발생.
- **결과**: 5분/1분마다 돌아가는 EXP 지급 로직이 매번 예외로 실패 → DB에 exp가 올라가지 않음 → 퇴장 시 `earned 0 exp`만 로그에 남음.

**조치**  
- DB 반영 버그 수정 시: aiosqlite에서 `cursor` 사용 방식을 맞추고(필요 시 `await conn.cursor()` 사용), 트랜잭션 커밋 순서를 “exp 먼저 커밋”으로 변경한 버전 적용 필요.

---

## 5. Discord API Rate Limit (2026-02-22 02:43~02:45)

- **종류**: `DELETE .../channels/1447457558762622976/messages/...` 요청에 대한 **429 (rate limited)**.
- **의미**: 한 채널에서 메시지 삭제를 짧은 시간에 많이 해서 Discord가 삭제 요청을 제한함.
- **대응**: 로그에 `Retrying in 0.xx seconds`가 찍혀 있어, 라이브러리가 자동 재시도한 상태. 이후 03:56, 07:05 등에 Gateway RESUMED가 다시 보이는 걸로 보아 봇은 계속 동작한 상태.

---

## 6. Heartbeat 지연 (2026-02-22 12:19:34)

- **로그**: `Shard ID None heartbeat blocked for more than 10 seconds`
- **Traceback**: `asyncio` → `selectors` → `poll(timeout, max_ev)` 에서 대기.
- **의미**: 이벤트 루프가 10초 이상 블로킹되어 Discord에 heartbeat를 제때 보내지 못한 상황. 라즈베리파이 CPU/메모리 부하나 디스크 I/O 등으로 인한 지연 가능성.
- **직후**: 12:19:35에 다시 `RESUMED` 로그가 있어 세션은 유지된 것으로 보임.

---

## 7. 요약 표

| 구분 | 내용 |
|------|------|
| 기동 | 정상 (DB 24명, 닉네임/역할 24명 갱신, 슬래시 6개 동기화) |
| Gateway | 중간중간 RESUMED 발생, 네트워크 재연결로 해석 가능 |
| 음성 EXP | 🎙️대화(5분/1exp), 📝-공부방-👥✅(1분/1exp) 에서 입·퇴장 정상 감지 |
| **EXP 지급** | **전부 실패** (`'Result' object has no attribute 'execute'` + `cursor` 미 await) → DB 미반영, earned 0 exp |
| Rate limit | 2026-02-22 02:43~02:45, 메시지 삭제 429 → 자동 재시도 |
| Heartbeat | 2026-02-22 12:19, 10초 이상 블로킹 1회 → 직후 RESUMED |

---

*이 정리는 “DB 반영 버그 수정, 레벨업 시 별명/역할 동기화, /스터디방확인 추가” 등 업데이트를 적용하기 **전** 로그를 기준으로 작성되었습니다.*
