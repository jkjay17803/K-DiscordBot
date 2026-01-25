# tier_roles_manager.py - 티어 역할 설정 파일 관리

import os
from typing import Dict, Tuple, Optional
from pathlib import Path

TIER_ROLES_FILE = "tier_roles.txt"


def ensure_file():
    """파일이 없으면 생성하고 config.py의 기본값으로 초기화"""
    if not os.path.exists(TIER_ROLES_FILE):
        # config.py에서 기본값 로드
        try:
            from config import _DEFAULT_TIER_ROLES as default_roles
        except ImportError:
            # _DEFAULT_TIER_ROLES가 없으면 빈 딕셔너리 사용
            default_roles = {}
        
        # 재귀 호출 없이 직접 파일에 쓰기
        try:
            with open(TIER_ROLES_FILE, 'w', encoding='utf-8') as f:
                # 티어 이름 순으로 정렬
                for tier_name, (required_level, role_name) in sorted(default_roles.items()):
                    f.write(f"{tier_name}:{required_level}:{role_name}\n")
        except Exception as e:
            print(f"[TierRolesManager] 파일 초기화 오류: {e}")


def load_tier_roles() -> Dict[str, Tuple[int, str]]:
    """
    tier_roles.txt 파일에서 설정 로드
    Returns: {티어_이름: (도달_레벨, 역할_이름)}
    """
    ensure_file()
    
    result = {}
    
    if not os.path.exists(TIER_ROLES_FILE):
        return result
    
    try:
        with open(TIER_ROLES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 형식: tier_name:required_level:role_name
                # 예: 브론즈:0:Bronze
                if ':' in line:
                    parts = line.split(':', 2)
                    if len(parts) == 3:
                        try:
                            tier_name = parts[0].strip()
                            required_level = int(parts[1].strip())
                            role_name = parts[2].strip()
                            
                            if required_level < 0:
                                continue
                            
                            result[tier_name] = (required_level, role_name)
                        except ValueError:
                            continue
    except Exception as e:
        print(f"[TierRolesManager] 파일 읽기 오류: {e}")
    
    return result


def save_tier_roles(tier_roles: Dict[str, Tuple[int, str]]):
    """
    tier_roles.txt 파일에 설정 저장
    Args:
        tier_roles: {티어_이름: (도달_레벨, 역할_이름)}
    """
    # 파일이 없으면 기본값으로 초기화 (재귀 호출 방지를 위해 직접 확인)
    if not os.path.exists(TIER_ROLES_FILE):
        ensure_file()
    
    try:
        with open(TIER_ROLES_FILE, 'w', encoding='utf-8') as f:
            # 티어 이름 순으로 정렬
            for tier_name, (required_level, role_name) in sorted(tier_roles.items()):
                f.write(f"{tier_name}:{required_level}:{role_name}\n")
    except Exception as e:
        print(f"[TierRolesManager] 파일 쓰기 오류: {e}")
        raise


def add_tier_role(tier_name: str, required_level: int, role_name: str) -> bool:
    """
    티어 역할 설정 추가
    Returns: 성공 여부
    """
    if required_level < 0:
        return False
    
    roles = load_tier_roles()
    roles[tier_name] = (required_level, role_name)
    save_tier_roles(roles)
    return True


def remove_tier_role(tier_name: str) -> Optional[Tuple[int, str]]:
    """
    티어 역할 설정 제거
    Returns: 삭제된 설정 (도달_레벨, 역할_이름) 또는 None
    """
    roles = load_tier_roles()
    
    if tier_name not in roles:
        return None
    
    removed = roles[tier_name]
    del roles[tier_name]
    save_tier_roles(roles)
    
    return removed


def update_tier_role(tier_name: str, required_level: int, role_name: str) -> bool:
    """
    티어 역할 설정 업데이트
    Returns: 성공 여부
    """
    if required_level < 0:
        return False
    
    return add_tier_role(tier_name, required_level, role_name)


def get_tier_role(tier_name: str) -> Optional[Tuple[int, str]]:
    """
    특정 티어의 설정 조회
    Returns: (도달_레벨, 역할_이름) 또는 None
    """
    roles = load_tier_roles()
    return roles.get(tier_name)

