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
import asyncio

from message_with_channel_id import message_with_channel_id
from database import init_database, initialize_all_members, get_user
from voice_monitor import setup_voice_monitor
from nickname_manager import initial_nickname_update, update_user_nickname, setup_nickname_update_event
from role_manager import initial_tier_role_update, update_tier_role
from level_system import set_level
from commands.slash_commands import setup_slash_commands

# Beta V2: Prefix 제거, Slash 명령어 사용
# 기존 Prefix 명령어는 하위 호환을 위해 유지 (level_command, market_command 등)
from commands.level_command import level_command
from commands.rank_command import rank_command
from commands.admin_command import admin_command
from commands.market_command import market_command
from commands.market_admin_command import market_admin_command
from commands.study_command import study_command
from commands.voice_channel_command import voice_channel_command
from commands.level_system_command import level_system_command
from commands.tier_system_command import tier_system_command
from commands.reboot_command import reboot_command

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.all()
k = commands.Bot(command_prefix='!', intents=intents)

# Slash 명령어는 on_ready에서 await setup_slash_commands(k)로 등록

# Prefix 명령어 (하위 호환 - Slash와 병행)
message_with_channel_id(k)
level_command(k)
rank_command(k)
admin_command(k)
market_command(k)
market_admin_command(k)
study_command(k)
voice_channel_command(k)
level_system_command(k)
tier_system_command(k)
reboot_command(k)

# onEnable
@k.event
async def on_ready():
    print(f"Logged in as {k.user}")

    # Slash 명령어 등록 (Beta V2) — async이므로 여기서 await
    await setup_slash_commands(k)

    # voice_channel_exp.txt 파일 초기화 (config.py 설정 마이그레이션)
    from voice_channel_exp_manager import load_voice_channel_exp, save_voice_channel_exp
    from config import VOICE_CHANNEL_EXP
    
    file_settings = load_voice_channel_exp()
    # 파일이 비어있고 config.py에 설정이 있으면 마이그레이션
    if not file_settings and VOICE_CHANNEL_EXP:
        save_voice_channel_exp(VOICE_CHANNEL_EXP)
        print(f"[VoiceChannelExp] Migrated {len(VOICE_CHANNEL_EXP)} settings from config.py to voice_channel_exp.txt")
    
    # level_ranges.txt 파일 초기화 (config.py 설정 마이그레이션)
    from level_ranges_manager import load_level_ranges, save_level_ranges, ensure_file
    from config import _DEFAULT_LEVEL_RANGES
    
    ensure_file()  # 파일이 없으면 기본값으로 생성
    file_level_ranges = load_level_ranges()
    # 파일이 비어있고 기본값이 있으면 마이그레이션
    if not file_level_ranges and _DEFAULT_LEVEL_RANGES:
        save_level_ranges(_DEFAULT_LEVEL_RANGES)
        print(f"[LevelRanges] Migrated {len(_DEFAULT_LEVEL_RANGES)} level ranges from config.py to level_ranges.txt")
    
    # tier_roles.txt 파일 초기화 (config.py 설정 마이그레이션)
    from tier_roles_manager import load_tier_roles, save_tier_roles, ensure_file as ensure_tier_file
    from config import _DEFAULT_TIER_ROLES
    
    ensure_tier_file()  # 파일이 없으면 기본값으로 생성
    file_tier_roles = load_tier_roles()
    # 파일이 비어있고 기본값이 있으면 마이그레이션
    if not file_tier_roles and _DEFAULT_TIER_ROLES:
        save_tier_roles(_DEFAULT_TIER_ROLES)
        print(f"[TierRoles] Migrated {len(_DEFAULT_TIER_ROLES)} tier roles from config.py to tier_roles.txt")
    
    # 데이터베이스 초기화 (SQLite, k_bot.db)
    try:
        await init_database()
        print("[Database] Database initialized")
        print("[Database] Initializing all members...")
        result = await initialize_all_members(k.guilds)
        print(f"[Database] Members initialized: {result['created']} created, {result['skipped']} already existed")
    except Exception as e:
        print(f"[Database] DB 초기화 실패 — 봇은 실행되지만 DB 기능은 사용할 수 없습니다: {e}")
    
    # 음성 모니터링 설정
    voice_monitor = setup_voice_monitor(k)
    k.voice_monitor = voice_monitor  # bot 객체에 저장하여 명령어에서 접근 가능하도록
    print("[VoiceMonitor] Voice monitoring enabled")
    
    # 봇 시작 시 이미 음성채널에 있는 사용자들 초기화
    await voice_monitor.initialize_existing_voice_users()
    
    # 처음 실행 시 모든 닉네임 즉시 업데이트
    await initial_nickname_update(k)

    # 처음 실행 시 모든 티어 역할 즉시 업데이트
    await initial_tier_role_update(k)

    # 닉네임 변경 이벤트 핸들러 설정 (이벤트 기반 업데이트)
    setup_nickname_update_event(k)
    print("[NicknameManager] Nickname update event handler registered (이벤트 기반)")

    # Slash 명령어 동기화 (Beta V2)
    try:
        from config import SLASH_SYNC_GUILD_ID
        if SLASH_SYNC_GUILD_ID:
            k.tree.copy_global_to(guild=discord.Object(id=SLASH_SYNC_GUILD_ID))
            synced = await k.tree.sync(guild=discord.Object(id=SLASH_SYNC_GUILD_ID))
            print(f"[Slash] 길드 동기화 완료: {len(synced)}개")
        else:
            synced = await k.tree.sync()
            print(f"[Slash] 글로벌 동기화 완료: {len(synced)}개")
    except Exception as e:
        print(f"[Slash] 동기화 오류: {e}")

    print("K 봇이 준비되었습니다!")


@k.event
async def on_member_join(member: discord.Member):
    """서버에 새 멤버가 들어왔을 때 처리"""
    # 봇은 제외
    if member.bot:
        return
    
    try:
        guild_id = member.guild.id
        user_id = member.id
        
        # 사용자가 데이터베이스에 이미 존재하는지 확인
        existing_user = await get_user(user_id, guild_id)
        
        # 처음 들어온 사람인 경우 (데이터베이스에 없음)
        if existing_user is None:
            print(f"[MemberJoin] New member joined: {member.name} (ID: {user_id})")
            
            # 레벨을 1로 설정
            await set_level(user_id, guild_id, 1)
            print(f"[MemberJoin] Set level to 1 for {member.name}")
            
            # 브론즈 티어 역할 부여 (레벨 1이면 자동으로 브론즈)
            success, old_tier, new_tier = await update_tier_role(member, 1)
            if success:
                print(f"[MemberJoin] Added Bronze tier role to {member.name}")
            else:
                print(f"[MemberJoin] Failed to add tier role to {member.name}")
            
            # 닉네임에 레벨 표시
            nickname_success = await update_user_nickname(member, 1)
            if nickname_success:
                print(f"[MemberJoin] Updated nickname for {member.name} with level 1")
            else:
                print(f"[MemberJoin] Failed to update nickname for {member.name}")
        else:
            # 이미 존재하는 사용자는 기존 레벨과 티어 유지
            print(f"[MemberJoin] Existing member rejoined: {member.name} (Level: {existing_user['level']})")
            
            # 닉네임과 티어 역할 동기화 (혹시 변경되었을 수 있으므로)
            await update_user_nickname(member, existing_user['level'])
            await update_tier_role(member, existing_user['level'])
    
    except Exception as e:
        print(f"[MemberJoin] Error processing member join for {member.name}: {e}")
        import traceback
        traceback.print_exc()
    

@k.event
async def on_command_error(ctx, error):
    """명령어 에러 핸들러"""
    # CommandNotFound 에러는 사용자에게 메시지 전송 (터미널 로그 방지)
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ `{ctx.invoked_with}` 명령어를 찾을 수 없습니다.")
        return
    
    # 명령어별 에러 핸들러가 있으면 그쪽에서 처리하도록 함
    # 여기서는 처리되지 않은 에러만 로깅
    if hasattr(ctx.command, 'on_error'):
        return
    
    # 처리되지 않은 에러는 로깅만 하고 사용자에게는 기본 메시지 전송
    import traceback
    print(f"[Command Error] {ctx.command.name if ctx.command else 'Unknown'}: {error}")
    print(traceback.format_exc())
    
    # 사용자에게는 간단한 메시지만 전송
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 필수 인자가 누락되었습니다. `!{ctx.command.name}` 명령어 사용법을 확인해주세요.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ 인자를 올바르게 입력해주세요. `!{ctx.command.name}` 명령어 사용법을 확인해주세요.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ 이 명령어를 사용할 권한이 없습니다.")
    elif isinstance(error, commands.CommandInvokeError) and error.original is not None:
        orig = error.original
        await ctx.send(f"❌ 명령어 실행 중 오류가 발생했습니다: {type(orig).__name__}: {orig}")
    else:
        await ctx.send(f"❌ 명령어 실행 중 오류가 발생했습니다: {type(error).__name__}")


#running - jk
k.run(TOKEN)
