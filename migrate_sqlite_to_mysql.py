#!/usr/bin/env python3
"""
SQLite(k_bot.db) → MySQL 데이터 마이그레이션 스크립트

사용법:
  1. 라즈베리파이의 K 폴더에서 실행 (k_bot.db가 같은 폴더에 있어야 함)
  2. .env에 MYSQL_* 설정이 있어야 함
  3. MySQL 서버가 실행 중이어야 함
  4. python migrate_sqlite_to_mysql.py

또는 SQLite 파일 경로 지정:
  python migrate_sqlite_to_mysql.py --sqlite-path /path/to/k_bot.db
"""

import asyncio
import argparse
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# MySQL 설정
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "k_bot")


def parse_sqlite_datetime(val):
    """SQLite ISO 형식 문자열 → MySQL datetime"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val)
    if not s:
        return None
    try:
        # SQLite: '2024-01-15 12:30:45' 또는 '2024-01-15T12:30:45'
        s = s.replace("T", " ")
        if "." in s:
            return datetime.strptime(s[:26], "%Y-%m-%d %H:%M:%S.%f")
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def migrate(sqlite_path: str):
    """SQLite → MySQL 마이그레이션 실행"""
    try:
        import aiomysql
    except ImportError:
        print("aiomysql이 설치되지 않았습니다. pip install aiomysql")
        return False

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    async def run():
        # MySQL 테이블 생성 (없으면)
        from database import init_database
        print("MySQL 테이블 확인/생성 중...")
        await init_database()
        print()

        conn = await aiomysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DATABASE,
            charset="utf8mb4",
        )
        try:
            async with conn.cursor() as cursor:
                # 1. users
                print("[1/5] users 테이블 마이그레이션...")
                rows = sqlite_conn.execute("SELECT * FROM users").fetchall()
                for row in rows:
                    last_voice = parse_sqlite_datetime(row["last_voice_join"])
                    last_nick = parse_sqlite_datetime(row["last_nickname_update"])
                    await cursor.execute(
                        """INSERT IGNORE INTO users 
                           (user_id, guild_id, level, exp, points, total_exp, last_voice_join, last_nickname_update)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            row["user_id"],
                            row["guild_id"],
                            row["level"],
                            row["exp"],
                            row["points"],
                            row["total_exp"],
                            last_voice,
                            last_nick,
                        ),
                    )
                print(f"  → {len(rows)} 행 이전")

                # 2. voice_sessions
                print("[2/5] voice_sessions 테이블 마이그레이션...")
                rows = sqlite_conn.execute("SELECT * FROM voice_sessions").fetchall()
                for row in rows:
                    join_t = parse_sqlite_datetime(row["join_time"])
                    leave_t = parse_sqlite_datetime(row["leave_time"])
                    await cursor.execute(
                        """INSERT INTO voice_sessions 
                           (session_id, user_id, guild_id, channel_id, join_time, leave_time, exp_earned)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            row["session_id"],
                            row["user_id"],
                            row["guild_id"],
                            row["channel_id"],
                            join_t,
                            leave_t,
                            row["exp_earned"],
                        ),
                    )
                print(f"  → {len(rows)} 행 이전")

                # 3. guild_settings
                print("[3/5] guild_settings 테이블 마이그레이션...")
                rows = sqlite_conn.execute("SELECT * FROM guild_settings").fetchall()
                for row in rows:
                    await cursor.execute(
                        """INSERT INTO guild_settings (guild_id, market_enabled)
                           VALUES (%s, %s)
                           ON DUPLICATE KEY UPDATE market_enabled = %s""",
                        (row["guild_id"], row["market_enabled"], row["market_enabled"]),
                    )
                print(f"  → {len(rows)} 행 이전")

                # 4. warnings
                print("[4/5] warnings 테이블 마이그레이션...")
                rows = sqlite_conn.execute("SELECT * FROM warnings").fetchall()
                for row in rows:
                    issued = parse_sqlite_datetime(row["issued_at"])
                    expires = parse_sqlite_datetime(row["expires_at"])
                    await cursor.execute(
                        """INSERT INTO warnings 
                           (warning_id, user_id, guild_id, reason, issued_at, issued_by, expires_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            row["warning_id"],
                            row["user_id"],
                            row["guild_id"],
                            row["reason"],
                            issued,
                            row["issued_by"],
                            expires,
                        ),
                    )
                print(f"  → {len(rows)} 행 이전")

                # 5. server_fees
                print("[5/5] server_fees 테이블 마이그레이션...")
                rows = sqlite_conn.execute("SELECT * FROM server_fees").fetchall()
                for row in rows:
                    created = parse_sqlite_datetime(row["created_at"])
                    await cursor.execute(
                        """INSERT INTO server_fees 
                           (fee_id, user_id, guild_id, amount, reason, transaction_type, created_at, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            row["fee_id"],
                            row["user_id"],
                            row["guild_id"],
                            row["amount"],
                            row["reason"],
                            row["transaction_type"],
                            created,
                            row["created_by"],
                        ),
                    )
                print(f"  → {len(rows)} 행 이전")

            await conn.commit()
            print("\n✅ 마이그레이션 완료!")
        finally:
            conn.close()

    sqlite_conn.close()

    asyncio.run(run())
    return True


def main():
    parser = argparse.ArgumentParser(description="SQLite → MySQL 마이그레이션")
    parser.add_argument(
        "--sqlite-path",
        default="k_bot.db",
        help="SQLite DB 파일 경로 (기본: k_bot.db)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.sqlite_path):
        print(f"❌ SQLite 파일을 찾을 수 없습니다: {args.sqlite_path}")
        print("   라즈베리파이 K 폴더에서 실행하거나 --sqlite-path로 경로를 지정하세요.")
        return 1

    print(f"SQLite: {args.sqlite_path}")
    print(f"MySQL: {MYSQL_USER}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    print()

    if migrate(args.sqlite_path):
        return 0
    return 1


if __name__ == "__main__":
    exit(main())
