# commands/reboot_command.py - JK 제부팅 명령어

import asyncio
import discord
from discord.ext import commands
from datetime import datetime
from database import get_all_users_for_nickname_refresh
from role_manager import update_tier_role
from utils import has_jk_role


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


def reboot_command(k):

    @k.command(name="jk제부팅")
    @check_jk()
    async def reboot_tier_system(ctx):
        """
        모든 사용자의 티어를 현재 .txt 파일 설정에 맞춰 재설정
        확인 절차를 거친 후 실행됩니다.
        """
        # 확인 메시지 전송
        embed = discord.Embed(
            title="⚠️ 티어 시스템 재설정 확인",
            description=(
                "이 명령어는 **모든 사용자의 티어 역할을 현재 설정 파일에 맞춰 재설정**합니다.\n\n"
                "**주의사항:**\n"
                "• 모든 서버의 모든 사용자가 영향을 받습니다\n"
                "• 티어 설정이 변경된 경우 사용자들의 티어가 자동으로 조정됩니다\n"
                "• 처리 시간이 다소 걸릴 수 있습니다\n\n"
                "계속하시려면 ✅ 이모지를 추가해주세요.\n"
                "취소하려면 ❌ 이모지를 추가해주세요."
            ),
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
        
        confirm_msg = await ctx.send(embed=embed)
        
        # 확인/취소 이모지 추가
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return (
                user == ctx.author
                and reaction.message.id == confirm_msg.id
                and str(reaction.emoji) in ["✅", "❌"]
            )
        
        try:
            # 60초 대기
            reaction, user = await k.wait_for("reaction_add", timeout=60.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await ctx.send("❌ 티어 시스템 재설정이 취소되었습니다.")
                return
            
            # 확인됨 - 재설정 시작
            await ctx.send("🔄 티어 시스템 재설정을 시작합니다...")
            
            # 진행 상황 메시지
            status_msg = await ctx.send("⏳ 사용자 조회 중...")
            
            # 모든 사용자 조회
            users = await get_all_users_for_nickname_refresh()
            total_users = len(users)
            
            if total_users == 0:
                await status_msg.edit(content="❌ 재설정할 사용자가 없습니다.")
                return
            
            await status_msg.edit(
                content=f"🔄 총 {total_users}명의 사용자 티어 재설정 중...\n"
                       f"⏳ 진행 중: 0/{total_users}"
            )
            
            # 통계
            updated_count = 0
            failed_count = 0
            skipped_count = 0
            tier_changes = {}  # {티어_이름: 변경_횟수}
            
            # 각 사용자 처리
            for idx, user_data in enumerate(users, 1):
                user_id = user_data['user_id']
                guild_id = user_data['guild_id']
                level = user_data['level']
                
                # 진행 상황 업데이트 (10명마다)
                if idx % 10 == 0 or idx == total_users:
                    await status_msg.edit(
                        content=f"🔄 총 {total_users}명의 사용자 티어 재설정 중...\n"
                               f"⏳ 진행 중: {idx}/{total_users} ({updated_count}명 업데이트, {failed_count}명 실패, {skipped_count}명 스킵)"
                    )
                
                # 서버 조회
                guild = ctx.bot.get_guild(guild_id)
                if guild is None:
                    skipped_count += 1
                    continue
                
                # 멤버 조회
                member = guild.get_member(user_id)
                if member is None:
                    skipped_count += 1
                    continue
                
                # 티어 역할 업데이트 (축하 메시지는 보내지 않음 - 재설정이므로)
                success, old_tier, new_tier = await update_tier_role(member, level)
                
                if success:
                    if old_tier != new_tier:
                        # 티어 변경 발생
                        updated_count += 1
                        if new_tier:
                            if new_tier not in tier_changes:
                                tier_changes[new_tier] = 0
                            tier_changes[new_tier] += 1
                    else:
                        # 티어 변경 없음
                        skipped_count += 1
                else:
                    failed_count += 1
                
                # API 레이트 리밋 방지를 위해 약간의 딜레이
                await asyncio.sleep(0.1)
            
            # 완료 메시지
            result_lines = [
                f"✅ 티어 시스템 재설정이 완료되었습니다!",
                "",
                f"**처리 결과:**",
                f"• 총 사용자: {total_users}명",
                f"• 티어 변경: {updated_count}명",
                f"• 변경 없음: {skipped_count}명",
                f"• 실패: {failed_count}명",
            ]
            
            if tier_changes:
                result_lines.append("")
                result_lines.append("**티어별 변경 통계:**")
                for tier_name, count in sorted(tier_changes.items(), key=lambda x: x[1], reverse=True):
                    result_lines.append(f"• {tier_name}: {count}명")
            
            result_embed = discord.Embed(
                title="✅ 티어 시스템 재설정 완료",
                description="\n".join(result_lines),
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            result_embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            
            await status_msg.edit(content="", embed=result_embed)
            
        except asyncio.TimeoutError:
            await ctx.send("❌ 확인 시간이 초과되었습니다. 티어 시스템 재설정이 취소되었습니다.")
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== 에러 핸들러 ==========
    @reboot_tier_system.error
    async def reboot_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 인자를 올바르게 입력해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

