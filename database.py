# database.py - 데이터베이스 관리

import aiosqlite
from datetime import datetime
from typing import Optional, List

DB_PATH = "k_bot.db"
DB_TIMEOUT = 30  # 잠금 시 대기 초 (database is locked 방지)


async def init_database():
    """데이터베이스 초기화 및 테이블 생성"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute("PRAGMA journal_mode=WAL")  # 동시 접근 시 잠금 완화
        # users 테이블
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                total_exp INTEGER DEFAULT 0,
                last_voice_join TIMESTAMP,
                last_nickname_update TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # voice_sessions 테이블
        await db.execute("""
            CREATE TABLE IF NOT EXISTS voice_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                join_time TIMESTAMP NOT NULL,
                leave_time TIMESTAMP,
                exp_earned INTEGER DEFAULT 0
            )
        """)
        
        # guild_settings 테이블
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                market_enabled INTEGER DEFAULT 1
            )
        """)
        
        # warnings 테이블
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                reason TEXT,
                issued_at TIMESTAMP NOT NULL,
                issued_by INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        
        # 인덱스 생성 (기존 인덱스가 있으면 무시됨)
        # users 테이블: guild_id로 조회 최적화
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_guild_id ON users(guild_id)
        """)
        
        # warnings 테이블: 만료 시간 조회 최적화
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_warnings_expires ON warnings(expires_at)
        """)
        
        # warnings 테이블: 사용자별 경고 조회 최적화
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_warnings_user_guild ON warnings(user_id, guild_id)
        """)
        
        # server_fees 테이블 (서버비 기록)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_fees (
                fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                created_by INTEGER NOT NULL
            )
        """)
        
        # server_fees 테이블 인덱스
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_server_fees_guild_id ON server_fees(guild_id)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_server_fees_created_at ON server_fees(created_at)
        """)
        
        await db.commit()


async def get_user(user_id: int, guild_id: int) -> Optional[dict]:
    """사용자 데이터 조회"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def create_user(user_id: int, guild_id: int) -> dict:
    """새 사용자 생성"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            """INSERT INTO users 
               (user_id, guild_id, level, exp, points, total_exp, last_nickname_update)
               VALUES (?, ?, 1, 0, 0, 0, ?)""",
            (user_id, guild_id, datetime.now().isoformat())
        )
        await db.commit()
    
    return await get_user(user_id, guild_id)


async def get_or_create_user(user_id: int, guild_id: int) -> dict:
    """사용자 조회, 없으면 생성"""
    user = await get_user(user_id, guild_id)
    if user is None:
        user = await create_user(user_id, guild_id)
    return user


async def update_user_exp(user_id: int, guild_id: int, exp: int, total_exp: int, db=None):
    """사용자 exp 업데이트"""
    if db is None:
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
            await db.execute(
                "UPDATE users SET exp = ?, total_exp = ? WHERE user_id = ? AND guild_id = ?",
                (exp, total_exp, user_id, guild_id)
            )
            await db.commit()
    else:
        # 트랜잭션 내에서 실행
        await db.execute(
            "UPDATE users SET exp = ?, total_exp = ? WHERE user_id = ? AND guild_id = ?",
            (exp, total_exp, user_id, guild_id)
        )


async def update_user_level(user_id: int, guild_id: int, level: int, exp: int, points: int, total_exp: int, db=None):
    """사용자 레벨, exp, 포인트, 총 exp 업데이트"""
    if db is None:
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
            await db.execute(
                """UPDATE users 
                   SET level = ?, exp = ?, points = ?, total_exp = ?
                   WHERE user_id = ? AND guild_id = ?""",
                (level, exp, points, total_exp, user_id, guild_id)
            )
            await db.commit()
    else:
        # 트랜잭션 내에서 실행
        await db.execute(
            """UPDATE users 
               SET level = ?, exp = ?, points = ?, total_exp = ?
               WHERE user_id = ? AND guild_id = ?""",
            (level, exp, points, total_exp, user_id, guild_id)
        )


async def update_user_points(user_id: int, guild_id: int, points: int):
    """사용자 포인트 업데이트"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            "UPDATE users SET points = ? WHERE user_id = ? AND guild_id = ?",
            (points, user_id, guild_id)
        )
        await db.commit()


async def update_last_voice_join(user_id: int, guild_id: int):
    """마지막 음성채널 입장 시간 업데이트"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            "UPDATE users SET last_voice_join = ? WHERE user_id = ? AND guild_id = ?",
            (datetime.now().isoformat(), user_id, guild_id)
        )
        await db.commit()


async def update_last_nickname_update(user_id: int, guild_id: int):
    """마지막 닉네임 업데이트 시간 기록"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            "UPDATE users SET last_nickname_update = ? WHERE user_id = ? AND guild_id = ?",
            (datetime.now().isoformat(), user_id, guild_id)
        )
        await db.commit()


async def create_voice_session(user_id: int, guild_id: int, channel_id: int) -> int:
    """음성 세션 생성"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        cursor = await db.execute(
            """INSERT INTO voice_sessions (user_id, guild_id, channel_id, join_time)
               VALUES (?, ?, ?, ?)""",
            (user_id, guild_id, channel_id, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def end_voice_session(session_id: int, exp_earned: int):
    """음성 세션 종료"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            """UPDATE voice_sessions 
               SET leave_time = ?, exp_earned = ?
               WHERE session_id = ?""",
            (datetime.now().isoformat(), exp_earned, session_id)
        )
        await db.commit()


async def get_leaderboard_by_points(guild_id: int, limit: int = 10) -> List[dict]:
    """포인트 기준 리더보드"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT user_id, level, exp, points, total_exp
               FROM users
               WHERE guild_id = ?
               ORDER BY points DESC, level DESC, total_exp DESC
               LIMIT ?""",
            (guild_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_leaderboard_by_level(guild_id: int, limit: int = 10) -> List[dict]:
    """레벨 기준 리더보드"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT user_id, level, exp, points, total_exp
               FROM users
               WHERE guild_id = ?
               ORDER BY level DESC, exp DESC, points DESC
               LIMIT ?""",
            (guild_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_user_rank_by_points(user_id: int, guild_id: int) -> int:
    """사용자의 포인트 기준 순위"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute(
            """SELECT COUNT(*) + 1 as rank
               FROM users
               WHERE guild_id = ? AND (
                   points > (SELECT points FROM users WHERE user_id = ? AND guild_id = ?)
                   OR (points = (SELECT points FROM users WHERE user_id = ? AND guild_id = ?)
                       AND level > (SELECT level FROM users WHERE user_id = ? AND guild_id = ?))
                   OR (points = (SELECT points FROM users WHERE user_id = ? AND guild_id = ?)
                       AND level = (SELECT level FROM users WHERE user_id = ? AND guild_id = ?)
                       AND total_exp > (SELECT total_exp FROM users WHERE user_id = ? AND guild_id = ?))
               )""",
            (guild_id, user_id, guild_id, user_id, guild_id, user_id, guild_id,
             user_id, guild_id, user_id, guild_id, user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1


async def get_user_rank_by_level(user_id: int, guild_id: int) -> int:
    """사용자의 레벨 기준 순위"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute(
            """SELECT COUNT(*) + 1 as rank
               FROM users
               WHERE guild_id = ? AND (
                   level > (SELECT level FROM users WHERE user_id = ? AND guild_id = ?)
                   OR (level = (SELECT level FROM users WHERE user_id = ? AND guild_id = ?)
                       AND exp > (SELECT exp FROM users WHERE user_id = ? AND guild_id = ?))
                   OR (level = (SELECT level FROM users WHERE user_id = ? AND guild_id = ?)
                       AND exp = (SELECT exp FROM users WHERE user_id = ? AND guild_id = ?)
                       AND points > (SELECT points FROM users WHERE user_id = ? AND guild_id = ?))
               )""",
            (guild_id, user_id, guild_id, user_id, guild_id, user_id, guild_id,
             user_id, guild_id, user_id, guild_id, user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 1


async def get_all_users_for_nickname_refresh(guild_id: Optional[int] = None) -> List[dict]:
    """닉네임 새로고침을 위한 모든 사용자 조회"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        if guild_id:
            async with db.execute(
                "SELECT user_id, guild_id, level FROM users WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        else:
            async with db.execute(
                "SELECT user_id, guild_id, level FROM users"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


async def initialize_all_members(guilds) -> dict:
    """
    모든 서버의 모든 멤버를 데이터베이스에 초기화
    Returns: {'created': int, 'skipped': int}
    """
    created = 0
    skipped = 0
    
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        for guild in guilds:
            if guild is None:
                continue
            
            # 서버의 모든 멤버 가져오기
            try:
                members = guild.members
                for member in members:
                    # 봇은 제외
                    if member.bot:
                        continue
                    
                    # 이미 존재하는지 확인
                    user = await get_user(member.id, guild.id)
                    if user is None:
                        # 새 사용자 생성
                        await create_user(member.id, guild.id)
                        created += 1
                    else:
                        skipped += 1
            except Exception as e:
                print(f"[Database] Error initializing members for {guild.name}: {e}")
                continue
    
    return {'created': created, 'skipped': skipped}


async def get_market_enabled(guild_id: int) -> bool:
    """마켓 활성화 상태 조회 (기본값: True)"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute(
            "SELECT market_enabled FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                # 기본값으로 설정 생성
                await set_market_enabled(guild_id, True)
                return True
            return bool(row[0])


async def set_market_enabled(guild_id: int, enabled: bool):
    """마켓 활성화 상태 설정"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            """INSERT OR REPLACE INTO guild_settings (guild_id, market_enabled)
               VALUES (?, ?)""",
            (guild_id, 1 if enabled else 0)
        )
        await db.commit()


# ========== 경고 시스템 함수들 ==========

async def add_warning(user_id: int, guild_id: int, reason: str, issued_by: int, warning_count: int = 1):
    """경고 추가"""
    from datetime import timedelta
    
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        issued_at = datetime.now()
        expires_at = issued_at + timedelta(days=7)
        
        for _ in range(warning_count):
            await db.execute(
                """INSERT INTO warnings (user_id, guild_id, reason, issued_at, issued_by, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, guild_id, reason, issued_at.isoformat(), issued_by, expires_at.isoformat())
            )
        
        await db.commit()


async def get_active_warning_count(user_id: int, guild_id: int) -> int:
    """활성 경고 수 조회 (모든 경고 - 자동 만료 없음)"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute(
            """SELECT COUNT(*) as count
               FROM warnings
               WHERE user_id = ? AND guild_id = ?""",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_warnings(user_id: int, guild_id: int) -> List[dict]:
    """사용자의 모든 경고 조회"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT warning_id, reason, issued_at, issued_by, expires_at
               FROM warnings
               WHERE user_id = ? AND guild_id = ?
               ORDER BY issued_at DESC""",
            (user_id, guild_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def remove_expired_warnings():
    """만료된 경고 삭제 (7일이 지난 경고)"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        cursor = await db.execute(
            """DELETE FROM warnings
               WHERE expires_at <= ?""",
            (datetime.now().isoformat(),)
        )
        await db.commit()
        return cursor.rowcount


async def remove_warnings(user_id: int, guild_id: int, count: int) -> int:
    """활성 경고 삭제 (가장 오래된 경고부터 삭제) - 자동 만료 없음"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        # 가장 오래된 경고부터 삭제
        cursor = await db.execute(
            """DELETE FROM warnings
               WHERE warning_id IN (
                   SELECT warning_id FROM warnings
                   WHERE user_id = ? AND guild_id = ?
                   ORDER BY issued_at ASC
                   LIMIT ?
               )""",
            (user_id, guild_id, count)
        )
        await db.commit()
        return cursor.rowcount


# ========== 서버비 시스템 함수들 ==========

async def add_server_fee(user_id: Optional[int], guild_id: int, amount: int, reason: str, created_by: int):
    """서버비 추가 기록"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            """INSERT INTO server_fees (user_id, guild_id, amount, reason, transaction_type, created_at, created_by)
               VALUES (?, ?, ?, ?, 'add', ?, ?)""",
            (user_id, guild_id, amount, reason, datetime.now().isoformat(), created_by)
        )
        await db.commit()


async def remove_server_fee(guild_id: int, amount: int, reason: str, created_by: int):
    """서버비 사용 기록"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        await db.execute(
            """INSERT INTO server_fees (user_id, guild_id, amount, reason, transaction_type, created_at, created_by)
               VALUES (NULL, ?, ?, ?, 'remove', ?, ?)""",
            (guild_id, amount, reason, datetime.now().isoformat(), created_by)
        )
        await db.commit()


async def get_server_fee_balance(guild_id: int) -> int:
    """서버비 잔액 조회 (추가된 금액 - 사용된 금액)"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        async with db.execute(
            """SELECT 
                   COALESCE(SUM(CASE WHEN transaction_type = 'add' THEN amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN transaction_type = 'remove' THEN amount ELSE 0 END), 0) as balance
               FROM server_fees
               WHERE guild_id = ?""",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_server_fee_history(guild_id: int, limit: int = 20) -> List[dict]:
    """서버비 기록 조회 (최근 기록부터)"""
    async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT fee_id, user_id, amount, reason, transaction_type, created_at, created_by
               FROM server_fees
               WHERE guild_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (guild_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

