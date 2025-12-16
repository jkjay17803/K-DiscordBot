# K.py - Main

r'''


         ,---._         ,--.
       .-- -.' \    ,--/  /|
       |    |   :,---,': / '
       :    ;   |:   : '/ /
       :        ||   '   ,
       |    :   :'   |  /
       :         |   ;  ;
       |    ;   |:   '   \ .
   ___ l         |   |    '
 /    /\    J   :'   : |.  \ .
/  ../  `..-    ,|   | '_\.'
\    \         ; '   : |
 \    \      ,'  ;   |,'
  "---....--'    '---'


'''
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

from message_with_channel_id import message_with_channel_id
from database import init_database, initialize_all_members
from voice_monitor import setup_voice_monitor
from nickname_manager import setup_nickname_refresh, initial_nickname_update
from commands.level_command import level_command
from commands.rank_command import rank_command
from commands.admin_command import admin_command

load_dotenv()

# .env
TOKEN = os.getenv("DISCORD_TOKEN")

# Permission - Intents
intents = discord.Intents.all()
# command - 정의
k = commands.Bot(command_prefix='!', intents=intents)

# modules
message_with_channel_id(k)
level_command(k)
rank_command(k)
admin_command(k)

# onEnable
@k.event
async def on_ready():
    print(f"Logged in as {k.user}")
    
    # 데이터베이스 초기화
    await init_database()
    print("[Database] Database initialized")
    
    # 모든 서버의 모든 멤버 초기화
    print("[Database] Initializing all members...")
    result = await initialize_all_members(k.guilds)
    print(f"[Database] Members initialized: {result['created']} created, {result['skipped']} already existed")
    
    # 음성 모니터링 설정
    voice_monitor = setup_voice_monitor(k)
    print("[VoiceMonitor] Voice monitoring enabled")
    
    # 봇 시작 시 이미 음성채널에 있는 사용자들 초기화
    await voice_monitor.initialize_existing_voice_users()
    
    # 처음 실행 시 모든 닉네임 즉시 업데이트
    await initial_nickname_update(k)

    # 닉네임 새로고침 백그라운드 작업 시작
    nickname_refresh_task = setup_nickname_refresh(k)
    print("[NicknameManager] Nickname refresh task started")
    
    print("K 봇이 준비되었습니다!")

#running - jk
k.run(TOKEN)
