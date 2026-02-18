# database.py - 데이터베이스 관리 (SQLite)

import os
import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List

# SQLite DB 경로 (.env 또는 기본값 k_bot.db)
DB_PATH = os.getenv("SQLITE_DB", "k_bot.db")


async def _get_connection():
    """SQLite 연결 생성 (row_factory=Row로 dict처럼 접근 가능)"""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def init_database():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = await _get_connection()
    try:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                total_exp INTEGER DEFAULT 0,
                last_voice_join TEXT,
                last_nickname_update TEXT,
                PRIMARY KEY (user_id, guild_id)
            );
            CREATE INDEX IF NOT EXISTS idx_users_guild_id ON users (guild_id);

            CREATE TABLE IF NOT EXISTS voice_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                join_time TEXT NOT NULL,
                leave_time TEXT,
                exp_earned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                market_enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS warnings (
                warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                reason TEXT,
                issued_at TEXT NOT NULL,
                issued_by INTEGER NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_warnings_expires ON warnings (expires_at);
            CREATE INDEX IF NOT EXISTS idx_warnings_user_guild ON warnings (user_id, guild_id);

            CREATE TABLE IF NOT EXISTS server_fees (
                fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_server_fees_guild_id ON server_fees (guild_id);
            CREATE INDEX IF NOT EXISTS idx_server_fees_created_at ON server_fees (created_at);
        """)
        await conn.commit()
    finally:
        await conn.close()


def _dt(val):
    """datetime → SQLite TEXT (ISO)"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S.%f")[:26]
    return str(val)


async def get_user(user_id: int, guild_id: int) -> Optional[dict]:
    """사용자 데이터 조회"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def create_user(user_id: int, guild_id: int) -> dict:
    """새 사용자 생성"""
    conn = await _get_connection()
    try:
        now = _dt(datetime.now())
        await conn.execute(
            """INSERT INTO users 
               (user_id, guild_id, level, exp, points, total_exp, last_nickname_update)
               VALUES (?, ?, 1, 0, 0, 0, ?)""",
            (user_id, guild_id, now)
        )
        await conn.commit()
    finally:
        await conn.close()
    return (await get_user(user_id, guild_id))


async def get_or_create_user(user_id: int, guild_id: int) -> dict:
    """사용자 조회, 없으면 생성"""
    user = await get_user(user_id, guild_id)
    if user is None:
        user = await create_user(user_id, guild_id)
    return user


async def update_user_exp(user_id: int, guild_id: int, exp: int, total_exp: int, cursor=None):
    """사용자 exp 업데이트 (cursor가 있으면 트랜잭션 내 실행, 호출자가 commit)"""
    if cursor is None:
        conn = await _get_connection()
        try:
            await conn.execute(
                "UPDATE users SET exp = ?, total_exp = ? WHERE user_id = ? AND guild_id = ?",
                (exp, total_exp, user_id, guild_id)
            )
            await conn.commit()
        finally:
            await conn.close()
    else:
        await cursor.execute(
            "UPDATE users SET exp = ?, total_exp = ? WHERE user_id = ? AND guild_id = ?",
            (exp, total_exp, user_id, guild_id)
        )


async def update_user_level(user_id: int, guild_id: int, level: int, exp: int, points: int, total_exp: int, cursor=None):
    """사용자 레벨, exp, 포인트, 총 exp 업데이트 (cursor가 있으면 트랜잭션 내 실행, 호출자가 commit)"""
    if cursor is None:
        conn = await _get_connection()
        try:
            await conn.execute(
                """UPDATE users 
                   SET level = ?, exp = ?, points = ?, total_exp = ?
                   WHERE user_id = ? AND guild_id = ?""",
                (level, exp, points, total_exp, user_id, guild_id)
            )
            await conn.commit()
        finally:
            await conn.close()
    else:
        await cursor.execute(
            """UPDATE users 
               SET level = ?, exp = ?, points = ?, total_exp = ?
               WHERE user_id = ? AND guild_id = ?""",
            (level, exp, points, total_exp, user_id, guild_id)
        )


async def update_user_points(user_id: int, guild_id: int, points: int):
    """사용자 포인트 업데이트"""
    conn = await _get_connection()
    try:
        await conn.execute(
            "UPDATE users SET points = ? WHERE user_id = ? AND guild_id = ?",
            (points, user_id, guild_id)
        )
        await conn.commit()
    finally:
        await conn.close()


async def update_last_voice_join(user_id: int, guild_id: int):
    """마지막 음성채널 입장 시간 업데이트"""
    conn = await _get_connection()
    try:
        await conn.execute(
            "UPDATE users SET last_voice_join = ? WHERE user_id = ? AND guild_id = ?",
            (_dt(datetime.now()), user_id, guild_id)
        )
        await conn.commit()
    finally:
        await conn.close()


async def update_last_nickname_update(user_id: int, guild_id: int):
    """마지막 닉네임 업데이트 시간 기록"""
    conn = await _get_connection()
    try:
        await conn.execute(
            "UPDATE users SET last_nickname_update = ? WHERE user_id = ? AND guild_id = ?",
            (_dt(datetime.now()), user_id, guild_id)
        )
        await conn.commit()
    finally:
        await conn.close()


async def create_voice_session(user_id: int, guild_id: int, channel_id: int) -> int:
    """음성 세션 생성"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """INSERT INTO voice_sessions (user_id, guild_id, channel_id, join_time)
               VALUES (?, ?, ?, ?)""",
            (user_id, guild_id, channel_id, _dt(datetime.now()))
        )
        session_id = cursor.lastrowid
        await conn.commit()
        return session_id
    finally:
        await conn.close()


async def end_voice_session(session_id: int, exp_earned: int):
    """음성 세션 종료"""
    conn = await _get_connection()
    try:
        await conn.execute(
            """UPDATE voice_sessions 
               SET leave_time = ?, exp_earned = ?
               WHERE session_id = ?""",
            (_dt(datetime.now()), exp_earned, session_id)
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_leaderboard_by_points(guild_id: int, limit: int = 10) -> List[dict]:
    """포인트 기준 리더보드"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """SELECT user_id, level, exp, points, total_exp
               FROM users
               WHERE guild_id = ?
               ORDER BY points DESC, level DESC, total_exp DESC
               LIMIT ?""",
            (guild_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_leaderboard_by_level(guild_id: int, limit: int = 10) -> List[dict]:
    """레벨 기준 리더보드"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """SELECT user_id, level, exp, points, total_exp
               FROM users
               WHERE guild_id = ?
               ORDER BY level DESC, exp DESC, points DESC
               LIMIT ?""",
            (guild_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_rank_by_points(user_id: int, guild_id: int) -> int:
    """사용자의 포인트 기준 순위"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
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
        )
        row = await cursor.fetchone()
        return row[0] if row else 1
    finally:
        await conn.close()


async def get_user_rank_by_level(user_id: int, guild_id: int) -> int:
    """사용자의 레벨 기준 순위"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
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
        )
        row = await cursor.fetchone()
        return row[0] if row else 1
    finally:
        await conn.close()


async def get_all_users_for_nickname_refresh(guild_id: Optional[int] = None) -> List[dict]:
    """닉네임 새로고침을 위한 모든 사용자 조회"""
    conn = await _get_connection()
    try:
        if guild_id:
            cursor = await conn.execute(
                "SELECT user_id, guild_id, level FROM users WHERE guild_id = ?",
                (guild_id,)
            )
        else:
            cursor = await conn.execute("SELECT user_id, guild_id, level FROM users")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def initialize_all_members(guilds) -> dict:
    """
    모든 서버의 모든 멤버를 데이터베이스에 초기화
    Returns: {'created': int, 'skipped': int}
    """
    created = 0
    skipped = 0
    for guild in guilds:
        if guild is None:
            continue
        try:
            for member in guild.members:
                if member.bot:
                    continue
                user = await get_user(member.id, guild.id)
                if user is None:
                    await create_user(member.id, guild.id)
                    created += 1
                else:
                    skipped += 1
        except Exception as e:
            print(f"[Database] Error initializing members for {guild.name}: {e}")
    return {'created': created, 'skipped': skipped}


async def get_market_enabled(guild_id: int) -> bool:
    """마켓 활성화 상태 조회 (기본값: True)"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            "SELECT market_enabled FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            await set_market_enabled(guild_id, True)
            return True
        return bool(row[0])
    finally:
        await conn.close()


async def set_market_enabled(guild_id: int, enabled: bool):
    """마켓 활성화 상태 설정"""
    conn = await _get_connection()
    try:
        await conn.execute(
            """INSERT INTO guild_settings (guild_id, market_enabled)
               VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET market_enabled = ?""",
            (guild_id, 1 if enabled else 0, 1 if enabled else 0)
        )
        await conn.commit()
    finally:
        await conn.close()


# ========== 경고 시스템 함수들 ==========

async def add_warning(user_id: int, guild_id: int, reason: str, issued_by: int, warning_count: int = 1):
    """경고 추가"""
    from datetime import timedelta
    conn = await _get_connection()
    try:
        issued_at = datetime.now()
        expires_at = issued_at + timedelta(days=7)
        for _ in range(warning_count):
            await conn.execute(
                """INSERT INTO warnings (user_id, guild_id, reason, issued_at, issued_by, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, guild_id, reason, _dt(issued_at), issued_by, _dt(expires_at))
            )
        await conn.commit()
    finally:
        await conn.close()


async def get_active_warning_count(user_id: int, guild_id: int) -> int:
    """활성 경고 수 조회"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """SELECT COUNT(*) as count
               FROM warnings
               WHERE user_id = ? AND guild_id = ?""",
            (user_id, guild_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await conn.close()


async def get_all_warnings(user_id: int, guild_id: int) -> List[dict]:
    """사용자의 모든 경고 조회"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """SELECT warning_id, reason, issued_at, issued_by, expires_at
               FROM warnings
               WHERE user_id = ? AND guild_id = ?
               ORDER BY issued_at DESC""",
            (user_id, guild_id)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def remove_expired_warnings():
    """만료된 경고 삭제 (7일이 지난 경고)"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            "DELETE FROM warnings WHERE expires_at <= ?",
            (_dt(datetime.now()),)
        )
        rowcount = cursor.rowcount
        await conn.commit()
        return rowcount
    finally:
        await conn.close()


async def remove_warnings(user_id: int, guild_id: int, count: int) -> int:
    """활성 경고 삭제 (가장 오래된 경고부터). SQLite는 같은 테이블 수정+서브쿼리 제한으로 두 단계 실행."""
    conn = await _get_connection()
    try:
        cur = await conn.execute(
            """SELECT warning_id FROM warnings
               WHERE user_id = ? AND guild_id = ?
               ORDER BY issued_at ASC
               LIMIT ?""",
            (user_id, guild_id, count)
        )
        ids = [row[0] for row in await cur.fetchall()]
        if not ids:
            return 0
        placeholders = ",".join("?" * len(ids))
        cur2 = await conn.execute(
            f"DELETE FROM warnings WHERE warning_id IN ({placeholders})",
            ids
        )
        rowcount = cur2.rowcount
        await conn.commit()
        return rowcount
    finally:
        await conn.close()


# ========== 서버비 시스템 함수들 ==========

async def add_server_fee(user_id: Optional[int], guild_id: int, amount: int, reason: str, created_by: int):
    """서버비 추가 기록"""
    conn = await _get_connection()
    try:
        await conn.execute(
            """INSERT INTO server_fees (user_id, guild_id, amount, reason, transaction_type, created_at, created_by)
               VALUES (?, ?, ?, ?, 'add', ?, ?)""",
            (user_id, guild_id, amount, reason, _dt(datetime.now()), created_by)
        )
        await conn.commit()
    finally:
        await conn.close()


async def remove_server_fee(guild_id: int, amount: int, reason: str, created_by: int):
    """서버비 사용 기록"""
    conn = await _get_connection()
    try:
        await conn.execute(
            """INSERT INTO server_fees (user_id, guild_id, amount, reason, transaction_type, created_at, created_by)
               VALUES (NULL, ?, ?, ?, 'remove', ?, ?)""",
            (guild_id, amount, reason, _dt(datetime.now()), created_by)
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_server_fee_balance(guild_id: int) -> int:
    """서버비 잔액 조회"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """SELECT 
                   COALESCE(SUM(CASE WHEN transaction_type = 'add' THEN amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN transaction_type = 'remove' THEN amount ELSE 0 END), 0) as balance
               FROM server_fees
               WHERE guild_id = ?""",
            (guild_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await conn.close()


async def get_server_fee_history(guild_id: int, limit: int = 20) -> List[dict]:
    """서버비 기록 조회 (최근 기록부터)"""
    conn = await _get_connection()
    try:
        cursor = await conn.execute(
            """SELECT fee_id, user_id, amount, reason, transaction_type, created_at, created_by
               FROM server_fees
               WHERE guild_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (guild_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ========== 트랜잭션 지원 (level_system add_exp용) ==========

async def get_mysql_connection():
    """트랜잭션용 DB 연결 반환 (호출자가 commit/rollback/close 책임). SQLite 사용 시에도 이름 유지."""
    return await _get_connection()
