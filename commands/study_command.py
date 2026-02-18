# commands/study_command.py - 스터디 명령어

import discord
from discord.ext import commands
from datetime import datetime
from study_manager import (
    add_member_to_study, remove_member_from_study,
    add_warning_to_study_member, remove_warning_from_study_member,
    get_study_channel_id, get_study_member_warning, get_study_member_info,
    read_study_file, create_study, delete_study
)
from utils import has_jk_role


def check_jk():
    """JK 역할을 가진 사용자만 사용 가능한 체크"""
    async def predicate(ctx):
        return has_jk_role(ctx.author)
    return commands.check(predicate)


class StudyDeleteConfirmView(discord.ui.View):
    """스터디 삭제 확인 버튼 뷰"""

    def __init__(self, study_name: str, member_count: int):
        super().__init__(timeout=60)
        self.study_name = study_name
        self.member_count = member_count
        self.deleted = False

    @discord.ui.button(label="✅ 삭제 확인", style=discord.ButtonStyle.red)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.deleted:
            await interaction.response.send_message("❌ 이미 삭제되었습니다.", ephemeral=True)
            return

        success = delete_study(self.study_name)
        
        if not success:
            await interaction.response.send_message(f"❌ `{self.study_name}` 스터디를 찾을 수 없습니다.", ephemeral=True)
            return
        
        self.deleted = True
        
        # 성공 메시지
        success_embed = discord.Embed(
            title="✅ 스터디 삭제 완료",
            description=f"**{self.study_name}** 스터디가 삭제되었습니다.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        success_embed.add_field(
            name="삭제된 정보",
            value=f"스터디 이름: {self.study_name}\n등록된 멤버: {self.member_count}명",
            inline=False
        )
        
        await interaction.response.edit_message(embed=success_embed, view=None)
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.grey)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cancel_embed = discord.Embed(
            title="❌ 삭제 취소",
            description="스터디 삭제가 취소되었습니다.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
    
    async def on_timeout(self):
        # 타임아웃 시 버튼 비활성화
        for item in self.children:
            item.disabled = True


def study_command(k):

    # ========== !jk스터디 명령어 그룹 ==========
    @k.group(name="jk스터디")
    @check_jk()
    async def jk_study_group(ctx):
        """JK 스터디 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk스터디 add [studyName] @플레이어` 또는 `!jk스터디 remove [studyName] @플레이어`")

    @jk_study_group.command(name="add")
    @check_jk()
    async def study_add_command(ctx, study_name: str = None, member: discord.Member = None, *memo_parts):
        """스터디에 플레이어 추가"""
        if study_name is None or member is None:
            await ctx.send("❌ 사용법: `!jk스터디 add [studyName] @플레이어 [메모]`\n예: `!jk스터디 add java @사용자 성빈이 형`")
            return
        
        # 메모 처리
        memo = " ".join(memo_parts) if memo_parts else ""
        
        try:
            success = add_member_to_study(study_name, member.id, memo)
            
            if not success:
                await ctx.send(f"❌ {member.display_name}님은 이미 `{study_name}` 스터디에 등록되어 있습니다.")
                return
            
            # 역할 부여
            role_added = False
            role_error = None
            try:
                role = discord.utils.get(ctx.guild.roles, name=study_name)
                if role:
                    await member.add_roles(role, reason=f"스터디 '{study_name}' 멤버 추가")
                    role_added = True
                else:
                    role_error = f"'{study_name}' 역할을 찾을 수 없습니다."
            except discord.Forbidden:
                role_error = "역할을 부여할 권한이 없습니다."
            except Exception as e:
                role_error = f"역할 부여 중 오류: {e}"
            
            embed = discord.Embed(
                title="✅ 스터디 멤버 추가 완료",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="스터디 이름",
                value=f"**{study_name}**",
                inline=False
            )
            embed.add_field(
                name="추가된 멤버",
                value=f"{member.display_name} ({member.mention})",
                inline=False
            )
            if role_added:
                embed.add_field(
                    name="역할 부여",
                    value=f"✅ **{study_name}** 역할이 부여되었습니다.",
                    inline=False
                )
            elif role_error:
                embed.add_field(
                    name="역할 부여",
                    value=f"⚠️ {role_error}",
                    inline=False
                )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
            # 회의실에 참가 메시지 전송
            channel_id = get_study_channel_id(study_name)
            if channel_id:
                try:
                    meeting_channel = ctx.bot.get_channel(channel_id)
                    if meeting_channel:
                        meeting_embed = discord.Embed(
                            title="✅ 스터디 참가",
                            description=f"{member.display_name} ({member.mention})님이 **{study_name}** 스터디에 참가했습니다.",
                            color=discord.Color.green(),
                            timestamp=datetime.now()
                        )
                        await meeting_channel.send(embed=meeting_embed)
                except Exception as e:
                    print(f"[StudyCommand] 회의실 메시지 전송 실패: {e}")
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_study_group.command(name="remove")
    @check_jk()
    async def study_remove_command(ctx, study_name: str = None, member: discord.Member = None):
        """스터디에서 플레이어 제거"""
        if study_name is None or member is None:
            await ctx.send("❌ 사용법: `!jk스터디 remove [studyName] @플레이어`\n예: `!jk스터디 remove java @사용자`")
            return
        
        try:
            success = remove_member_from_study(study_name, member.id)
            
            if not success:
                await ctx.send(f"❌ {member.display_name}님은 `{study_name}` 스터디에 등록되어 있지 않습니다.")
                return
            
            # 역할 제거
            role_removed = False
            role_error = None
            try:
                role = discord.utils.get(ctx.guild.roles, name=study_name)
                if role:
                    await member.remove_roles(role, reason=f"스터디 '{study_name}' 멤버 제거")
                    role_removed = True
                else:
                    role_error = f"'{study_name}' 역할을 찾을 수 없습니다."
            except discord.Forbidden:
                role_error = "역할을 제거할 권한이 없습니다."
            except Exception as e:
                role_error = f"역할 제거 중 오류: {e}"
            
            embed = discord.Embed(
                title="✅ 스터디 멤버 제거 완료",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="스터디 이름",
                value=f"**{study_name}**",
                inline=False
            )
            embed.add_field(
                name="제거된 멤버",
                value=f"{member.display_name} ({member.mention})",
                inline=False
            )
            if role_removed:
                embed.add_field(
                    name="역할 제거",
                    value=f"✅ **{study_name}** 역할이 제거되었습니다.",
                    inline=False
                )
            elif role_error:
                embed.add_field(
                    name="역할 제거",
                    value=f"⚠️ {role_error}",
                    inline=False
                )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
            # 회의실에 퇴장 메시지 전송
            channel_id = get_study_channel_id(study_name)
            if channel_id:
                try:
                    meeting_channel = ctx.bot.get_channel(channel_id)
                    if meeting_channel:
                        meeting_embed = discord.Embed(
                            title="👋 스터디 퇴장",
                            description=f"{member.display_name} ({member.mention})님이 **{study_name}** 스터디에서 퇴장했습니다.",
                            color=discord.Color.orange(),
                            timestamp=datetime.now()
                        )
                        await meeting_channel.send(embed=meeting_embed)
                except Exception as e:
                    print(f"[StudyCommand] 회의실 메시지 전송 실패: {e}")
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_study_group.command(name="log")
    @check_jk()
    async def study_log_command(ctx, study_name: str = None, member: discord.Member = None):
        """스터디 멤버의 경고 수 확인 (멤버 생략 시 전체 멤버 정보 표시)"""
        if study_name is None:
            await ctx.send("❌ 사용법: `!jk스터디 log [studyName] [@플레이어]`\n예: `!jk스터디 log java @사용자` 또는 `!jk스터디 log java`")
            return
        
        try:
            from study_manager import read_study_file
            
            # 멤버가 지정된 경우: 개별 멤버 정보 표시
            if member is not None:
                member_info = get_study_member_info(study_name, member.id)
                
                if member_info is None:
                    await ctx.send(f"❌ {member.display_name}님은 `{study_name}` 스터디에 등록되어 있지 않습니다.")
                    return
                
                warning_count, memo = member_info
                
                embed = discord.Embed(
                    title="📋 스터디 멤버 정보",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="스터디 이름",
                    value=f"**{study_name}**",
                    inline=False
                )
                embed.add_field(
                    name="멤버",
                    value=f"{member.display_name} ({member.mention})",
                    inline=False
                )
                embed.add_field(
                    name="경고 수",
                    value=f"**{warning_count}개**",
                    inline=True
                )
                if memo:
                    embed.add_field(
                        name="메모",
                        value=memo,
                        inline=False
                    )
                embed.set_footer(text=f"조회자: {ctx.author.display_name}")
                await ctx.send(embed=embed)
            
            # 멤버가 지정되지 않은 경우: 전체 멤버 정보 표시
            else:
                channel_id, members = read_study_file(study_name)
                
                if not members:
                    await ctx.send(f"❌ `{study_name}` 스터디에 등록된 멤버가 없습니다.")
                    return
                
                embed = discord.Embed(
                    title=f"📋 {study_name} 스터디 전체 멤버 정보",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                # 멤버 정보 수집
                member_list = []
                for user_id, (warning_count, memo) in sorted(members.items(), key=lambda x: x[1][0], reverse=True):  # 경고 수 기준 내림차순
                    try:
                        discord_member = ctx.guild.get_member(user_id)
                        if discord_member:
                            member_name = f"{discord_member.display_name} ({discord_member.mention})"
                        else:
                            member_name = f"ID: {user_id} (서버에 없음)"
                    except:
                        member_name = f"ID: {user_id}"
                    
                    memo_text = f" - {memo}" if memo else ""
                    member_list.append(f"{member_name}: **{warning_count}개**{memo_text}")
                
                # Discord 임베드 필드 제한(25개)을 고려하여 여러 필드로 나누기
                # 각 필드는 최대 1024자이므로 적절히 분할
                field_value = ""
                field_count = 0
                for member_info in member_list:
                    if len(field_value) + len(member_info) + 2 > 1024:  # +2는 줄바꿈 문자
                        embed.add_field(
                            name=f"멤버 목록 ({field_count + 1})",
                            value=field_value,
                            inline=False
                        )
                        field_value = member_info + "\n"
                        field_count += 1
                    else:
                        field_value += member_info + "\n"
                
                # 마지막 필드 추가
                if field_value:
                    embed.add_field(
                        name=f"멤버 목록 ({field_count + 1})" if field_count > 0 else "멤버 목록",
                        value=field_value,
                        inline=False
                    )
                
                embed.add_field(
                    name="총 멤버 수",
                    value=f"**{len(members)}명**",
                    inline=True
                )
                embed.set_footer(text=f"조회자: {ctx.author.display_name}")
                await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== !jk스터디 study 명령어 그룹 ==========
    @jk_study_group.group(name="study")
    @check_jk()
    async def jk_study_manage_group(ctx):
        """JK 스터디 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk스터디 study add [studyName] [회의실ID]` 또는 `!jk스터디 study remove [studyName]`")

    @jk_study_manage_group.command(name="add")
    @check_jk()
    async def study_create_command(ctx, study_name: str = None, channel_id: int = None):
        """스터디 생성 및 회의실 ID 설정"""
        if study_name is None or channel_id is None:
            await ctx.send("❌ 사용법: `!jk스터디 study add [studyName] [회의실ID]`\n예: `!jk스터디 study add Java 123456789012345678`")
            return
        
        try:
            # 채널 존재 확인
            channel = ctx.bot.get_channel(channel_id)
            if channel is None:
                await ctx.send(f"❌ 회의실 ID `{channel_id}`를 찾을 수 없습니다.")
                return
            
            # 스터디 생성
            success = create_study(study_name, channel_id)
            
            if not success:
                await ctx.send(f"❌ `{study_name}` 스터디가 이미 존재합니다.")
                return
            
            embed = discord.Embed(
                title="✅ 스터디 생성 완료",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="스터디 이름",
                value=f"**{study_name}**",
                inline=False
            )
            embed.add_field(
                name="회의실",
                value=f"{channel.mention} (ID: {channel_id})",
                inline=False
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_study_manage_group.command(name="remove")
    @check_jk()
    async def study_delete_command(ctx, study_name: str = None):
        """스터디 삭제 (확인 절차 필요)"""
        if study_name is None:
            await ctx.send("❌ 사용법: `!jk스터디 study remove [studyName]`\n예: `!jk스터디 study remove Java`")
            return
        
        try:
            # 스터디 존재 확인
            channel_id, members = read_study_file(study_name)
            if channel_id is None and not members:
                await ctx.send(f"❌ `{study_name}` 스터디를 찾을 수 없습니다.")
                return
            
            # 확인 임베드 생성
            embed = discord.Embed(
                title="⚠️ 스터디 삭제 확인",
                description=f"**{study_name}** 스터디를 정말 삭제하시겠습니까?",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="스터디 정보",
                value=f"**이름:** {study_name}\n**등록된 멤버:** {len(members)}명",
                inline=False
            )
            embed.add_field(
                name="⚠️ 경고",
                value="이 작업은 되돌릴 수 없습니다. 모든 멤버 정보와 경고 기록이 삭제됩니다.",
                inline=False
            )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            
            # 확인 버튼 생성
            view = StudyDeleteConfirmView(study_name, len(members))
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== !jk스터디 warning 명령어 그룹 ==========
    @jk_study_group.group(name="warning")
    @check_jk()
    async def jk_study_warning_group(ctx):
        """JK 스터디 경고 관리 명령어 그룹"""
        if ctx.invoked_subcommand is None:
            await ctx.send("❌ 사용법: `!jk스터디 warning add [studyName] @플레이어 [사유]` 또는 `!jk스터디 warning remove [studyName] @플레이어`")

    @jk_study_warning_group.command(name="add")
    @check_jk()
    async def study_warning_add_command(ctx, study_name: str = None, member: discord.Member = None, *reason_parts):
        """스터디 경고 부여"""
        if study_name is None or member is None:
            await ctx.send("❌ 사용법: `!jk스터디 warning add [studyName] @플레이어 [사유]`\n예: `!jk스터디 warning add java @사용자 지각`")
            return
        
        # 사유 처리
        if not reason_parts:
            reason_text = "사유 없음"
        else:
            reason_text = " ".join(reason_parts)
        if reason_text.strip() == "":
            reason_text = "사유 없음"
        
        try:
            # 경고 추가
            success, new_warning_count = add_warning_to_study_member(study_name, member.id, 1)
            
            if not success:
                await ctx.send(f"❌ {member.display_name}님은 `{study_name}` 스터디에 등록되어 있지 않습니다.")
                return
            
            # 회의실 ID 가져오기
            channel_id = get_study_channel_id(study_name)
            
            # 회의실에 로그 전송
            if channel_id:
                try:
                    log_channel = ctx.bot.get_channel(channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="⚠️ 스터디 경고 부여",
                            color=discord.Color.orange(),
                            timestamp=datetime.now()
                        )
                        embed.add_field(
                            name="스터디 이름",
                            value=f"**{study_name}**",
                            inline=False
                        )
                        embed.add_field(
                            name="대상 사용자",
                            value=f"{member.display_name} ({member.mention})",
                            inline=False
                        )
                        embed.add_field(
                            name="부여된 경고",
                            value=f"**+1개**",
                            inline=True
                        )
                        embed.add_field(
                            name="총 경고 수",
                            value=f"**{new_warning_count}개**",
                            inline=True
                        )
                        embed.add_field(
                            name="사유",
                            value=reason_text,
                            inline=False
                        )
                        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
                        await log_channel.send(embed=embed)
                except Exception as e:
                    print(f"[StudyCommand] 회의실 로그 전송 실패: {e}")
            
            # 응답 임베드 생성
            embed = discord.Embed(
                title="✅ 스터디 경고 부여 완료",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="스터디 이름",
                value=f"**{study_name}**",
                inline=False
            )
            embed.add_field(
                name="대상 사용자",
                value=f"{member.display_name} ({member.mention})",
                inline=False
            )
            embed.add_field(
                name="부여된 경고",
                value=f"**+1개**",
                inline=True
            )
            embed.add_field(
                name="총 경고 수",
                value=f"**{new_warning_count}개**",
                inline=True
            )
            embed.add_field(
                name="사유",
                value=reason_text,
                inline=False
            )
            if channel_id:
                log_channel = ctx.bot.get_channel(channel_id)
                if log_channel:
                    embed.add_field(
                        name="로그 전송",
                        value=f"✅ {log_channel.mention}에 로그가 전송되었습니다.",
                        inline=False
                    )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    @jk_study_warning_group.command(name="remove")
    @check_jk()
    async def study_warning_remove_command(ctx, study_name: str = None, member: discord.Member = None):
        """스터디 경고 제거"""
        if study_name is None or member is None:
            await ctx.send("❌ 사용법: `!jk스터디 warning remove [studyName] @플레이어`\n예: `!jk스터디 warning remove java @사용자`")
            return
        
        try:
            # 현재 경고 점수 확인
            current_warning = get_study_member_warning(study_name, member.id)
            if current_warning is None:
                await ctx.send(f"❌ {member.display_name}님은 `{study_name}` 스터디에 등록되어 있지 않습니다.")
                return
            
            if current_warning == 0:
                await ctx.send(f"❌ {member.display_name}님의 `{study_name}` 스터디 경고가 0개입니다.")
                return
            
            # 경고 제거
            success, new_warning_count = remove_warning_from_study_member(study_name, member.id, 1)
            
            if not success:
                await ctx.send(f"❌ 경고 제거에 실패했습니다.")
                return
            
            # 회의실 ID 가져오기
            channel_id = get_study_channel_id(study_name)
            
            # 회의실에 로그 전송
            if channel_id:
                try:
                    log_channel = ctx.bot.get_channel(channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="✅ 스터디 경고 제거",
                            color=discord.Color.green(),
                            timestamp=datetime.now()
                        )
                        embed.add_field(
                            name="스터디 이름",
                            value=f"**{study_name}**",
                            inline=False
                        )
                        embed.add_field(
                            name="대상 사용자",
                            value=f"{member.display_name} ({member.mention})",
                            inline=False
                        )
                        embed.add_field(
                            name="제거된 경고",
                            value=f"**-1개**",
                            inline=True
                        )
                        embed.add_field(
                            name="총 경고 수",
                            value=f"**{new_warning_count}개**",
                            inline=True
                        )
                        embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
                        await log_channel.send(embed=embed)
                except Exception as e:
                    print(f"[StudyCommand] 회의실 로그 전송 실패: {e}")
            
            # 응답 임베드 생성
            embed = discord.Embed(
                title="✅ 스터디 경고 제거 완료",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="스터디 이름",
                value=f"**{study_name}**",
                inline=False
            )
            embed.add_field(
                name="대상 사용자",
                value=f"{member.display_name} ({member.mention})",
                inline=False
            )
            embed.add_field(
                name="제거된 경고",
                value=f"**-1개**",
                inline=True
            )
            embed.add_field(
                name="총 경고 수",
                value=f"**{new_warning_count}개**",
                inline=True
            )
            if channel_id:
                log_channel = ctx.bot.get_channel(channel_id)
                if log_channel:
                    embed.add_field(
                        name="로그 전송",
                        value=f"✅ {log_channel.mention}에 로그가 전송되었습니다.",
                        inline=False
                    )
            embed.set_footer(text=f"명령어 실행자: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 오류가 발생했습니다: {e}")
            import traceback
            traceback.print_exc()

    # ========== 에러 핸들러 ==========
    @study_add_command.error
    @study_remove_command.error
    @study_log_command.error
    @study_create_command.error
    @study_delete_command.error
    @study_warning_add_command.error
    @study_warning_remove_command.error
    async def study_command_error(ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 이 명령어는 JK 역할을 가진 사용자만 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 사용법을 확인해주세요.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 사용자를 올바르게 멘션해주세요.")
        else:
            await ctx.send(f"❌ 오류가 발생했습니다: {error}")

