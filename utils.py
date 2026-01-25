# utils.py - 공통 유틸리티 함수

import discord


def has_jk_role(member: discord.Member) -> bool:
    """사용자가 JK 역할을 가지고 있는지 확인"""
    return any(role.name == "JK" for role in member.roles)

