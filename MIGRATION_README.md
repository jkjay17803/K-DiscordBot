# SQLite → MySQL 마이그레이션 가이드

## 사전 준비

### 1. 라즈베리파이에 MySQL 설치

```bash
sudo apt update
sudo apt install mysql-server
sudo mysql_secure_installation
```

### 2. 데이터베이스 및 사용자 생성

```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE k_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'k_bot'@'localhost' IDENTIFIED BY '비밀번호';
GRANT ALL PRIVILEGES ON k_bot.* TO 'k_bot'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. .env 설정

`env.example`을 참고하여 `.env` 파일에 MySQL 설정 추가:

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=k_bot
MYSQL_PASSWORD=비밀번호
MYSQL_DATABASE=k_bot
```

## 마이그레이션 순서

1. **봇 중지** (실행 중이면 종료)

2. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **라즈베리파이 K 폴더에서 마이그레이션 실행**
   ```bash
   cd ~/K   # 또는 k_bot.db가 있는 경로
   python migrate_sqlite_to_mysql.py
   ```

   SQLite 파일이 다른 경로에 있으면:
   ```bash
   python migrate_sqlite_to_mysql.py --sqlite-path /경로/k_bot.db
   ```

4. **마이그레이션 완료 후 봇 실행**
   ```bash
   python K.py
   ```

## 주의사항

- 마이그레이션 전 `k_bot.db` 백업 권장
- 기존 MySQL에 데이터가 있으면 `INSERT IGNORE`/`ON DUPLICATE KEY`로 중복 방지
- SQLite 파일(`k_bot.db`)은 마이그레이션 후에도 보관해 두었다가, 문제 없이 동작하는지 확인한 뒤 삭제
