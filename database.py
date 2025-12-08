# database.py - 데이터베이스 관리

import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List, Tuple

DB_PATH = "k_bot.db"


async def init_database():
    """데이터베이스 초기화 및 테이블 생성"""
    async with aiosqlite.connect(DB_PATH) as db:
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
        
        await db.commit()


async def get_user(user_id: int, guild_id: int) -> Optional[dict]:
    """사용자 데이터 조회"""
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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


async def update_user_exp(user_id: int, guild_id: int, exp: int, total_exp: int):
    """사용자 exp 업데이트"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET exp = ?, total_exp = ? WHERE user_id = ? AND guild_id = ?",
            (exp, total_exp, user_id, guild_id)
        )
        await db.commit()


async def update_user_level(user_id: int, guild_id: int, level: int, exp: int, points: int):
    """사용자 레벨, exp, 포인트 업데이트"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE users 
               SET level = ?, exp = ?, points = ?
               WHERE user_id = ? AND guild_id = ?""",
            (level, exp, points, user_id, guild_id)
        )
        await db.commit()


async def update_user_points(user_id: int, guild_id: int, points: int):
    """사용자 포인트 업데이트"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET points = ? WHERE user_id = ? AND guild_id = ?",
            (points, user_id, guild_id)
        )
        await db.commit()


async def update_last_voice_join(user_id: int, guild_id: int):
    """마지막 음성채널 입장 시간 업데이트"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_voice_join = ? WHERE user_id = ? AND guild_id = ?",
            (datetime.now().isoformat(), user_id, guild_id)
        )
        await db.commit()


async def update_last_nickname_update(user_id: int, guild_id: int):
    """마지막 닉네임 업데이트 시간 기록"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_nickname_update = ? WHERE user_id = ? AND guild_id = ?",
            (datetime.now().isoformat(), user_id, guild_id)
        )
        await db.commit()


async def create_voice_session(user_id: int, guild_id: int, channel_id: int) -> int:
    """음성 세션 생성"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO voice_sessions (user_id, guild_id, channel_id, join_time)
               VALUES (?, ?, ?, ?)""",
            (user_id, guild_id, channel_id, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid


async def end_voice_session(session_id: int, exp_earned: int):
    """음성 세션 종료"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE voice_sessions 
               SET leave_time = ?, exp_earned = ?
               WHERE session_id = ?""",
            (datetime.now().isoformat(), exp_earned, session_id)
        )
        await db.commit()


async def get_leaderboard_by_points(guild_id: int, limit: int = 10) -> List[dict]:
    """포인트 기준 리더보드"""
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    
    async with aiosqlite.connect(DB_PATH) as db:
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

