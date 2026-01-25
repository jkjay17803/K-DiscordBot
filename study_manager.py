# study_manager.py - 스터디 파일 관리

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

STUDY_DIR = "study"


def ensure_study_dir():
    """스터디 폴더가 없으면 생성"""
    Path(STUDY_DIR).mkdir(exist_ok=True)


def get_study_file_path(study_name: str) -> str:
    """스터디 파일 경로 반환 (대소문자 구분 없이 찾기)"""
    ensure_study_dir()
    
    # 먼저 정확한 이름으로 찾기
    filename = f"study_{study_name}.txt"
    filepath = os.path.join(STUDY_DIR, filename)
    
    if os.path.exists(filepath):
        return filepath
    
    # 대소문자 구분 없이 찾기
    if os.path.exists(STUDY_DIR):
        for file in os.listdir(STUDY_DIR):
            if file.lower() == filename.lower():
                return os.path.join(STUDY_DIR, file)
    
    # 파일이 없으면 정확한 이름으로 반환 (새로 만들 때 사용)
    return filepath


def read_study_file(study_name: str) -> Tuple[Optional[int], Dict[int, Tuple[int, str]]]:
    """
    스터디 파일 읽기
    Returns: (회의실_ID, {user_id: (경고점수, 메모)})
    """
    filepath = get_study_file_path(study_name)
    
    if not os.path.exists(filepath):
        return None, {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return None, {}
        
        # 첫 줄: 회의실 ID
        channel_id = None
        try:
            channel_id = int(lines[0].strip())
        except (ValueError, IndexError):
            pass
        
        # 나머지 줄: user_id:경고점수 #메모 또는 user_id:경고점수
        members = {}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            if ':' in line:
                # # 기호로 메모 분리
                if '#' in line:
                    main_part, memo = line.split('#', 1)
                    memo = memo.strip()
                else:
                    main_part = line
                    memo = ""
                
                # user_id:경고점수 파싱
                parts = main_part.split(':', 1)
                try:
                    user_id = int(parts[0].strip())
                    warning_count = int(parts[1].strip())
                    members[user_id] = (warning_count, memo)
                except (ValueError, IndexError):
                    continue
        
        return channel_id, members
    except Exception as e:
        print(f"[StudyManager] 파일 읽기 오류 ({study_name}): {e}")
        return None, {}


def write_study_file(study_name: str, channel_id: Optional[int], members: Dict[int, Tuple[int, str]]):
    """스터디 파일 쓰기"""
    filepath = get_study_file_path(study_name)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # 첫 줄: 회의실 ID
            if channel_id is not None:
                f.write(f"{channel_id}\n")
            else:
                f.write("0\n")
            
            # 나머지 줄: user_id:경고점수 #메모 또는 user_id:경고점수
            for user_id, (warning_count, memo) in sorted(members.items()):
                if memo:
                    f.write(f"{user_id}:{warning_count} # {memo}\n")
                else:
                    f.write(f"{user_id}:{warning_count}\n")
    except Exception as e:
        print(f"[StudyManager] 파일 쓰기 오류 ({study_name}): {e}")
        raise


def add_member_to_study(study_name: str, user_id: int, memo: str = "") -> bool:
    """스터디에 멤버 추가"""
    channel_id, members = read_study_file(study_name)
    
    # 이미 존재하는 경우
    if user_id in members:
        return False
    
    # 멤버 추가 (경고 점수 0으로 시작, 메모 포함)
    members[user_id] = (0, memo)
    write_study_file(study_name, channel_id, members)
    return True


def remove_member_from_study(study_name: str, user_id: int) -> bool:
    """스터디에서 멤버 제거"""
    channel_id, members = read_study_file(study_name)
    
    # 존재하지 않는 경우
    if user_id not in members:
        return False
    
    # 멤버 제거
    del members[user_id]
    write_study_file(study_name, channel_id, members)
    return True


def add_warning_to_study_member(study_name: str, user_id: int, warning_count: int = 1) -> Tuple[bool, int]:
    """
    스터디 멤버에게 경고 추가
    Returns: (성공여부, 새로운 경고 점수)
    """
    channel_id, members = read_study_file(study_name)
    
    # 멤버가 없는 경우
    if user_id not in members:
        return False, 0
    
    # 경고 추가 (메모는 유지)
    current_warning, memo = members.get(user_id, (0, ""))
    new_warning_count = current_warning + warning_count
    members[user_id] = (new_warning_count, memo)
    write_study_file(study_name, channel_id, members)
    return True, new_warning_count


def remove_warning_from_study_member(study_name: str, user_id: int, warning_count: int = 1) -> Tuple[bool, int]:
    """
    스터디 멤버의 경고 제거
    Returns: (성공여부, 새로운 경고 점수)
    """
    channel_id, members = read_study_file(study_name)
    
    # 멤버가 없는 경우
    if user_id not in members:
        return False, 0
    
    # 경고 제거 (메모는 유지)
    current_warning, memo = members.get(user_id, (0, ""))
    new_warning = max(0, current_warning - warning_count)
    members[user_id] = (new_warning, memo)
    write_study_file(study_name, channel_id, members)
    return True, new_warning


def get_study_member_warning(study_name: str, user_id: int) -> Optional[int]:
    """스터디 멤버의 경고 점수 조회"""
    _, members = read_study_file(study_name)
    member_data = members.get(user_id)
    if member_data is None:
        return None
    return member_data[0]  # 경고 점수만 반환


def get_study_member_info(study_name: str, user_id: int) -> Optional[Tuple[int, str]]:
    """스터디 멤버의 경고 점수와 메모 조회"""
    _, members = read_study_file(study_name)
    return members.get(user_id)  # (경고점수, 메모) 또는 None


def get_study_channel_id(study_name: str) -> Optional[int]:
    """스터디의 회의실 ID 조회"""
    channel_id, _ = read_study_file(study_name)
    return channel_id


def set_study_channel_id(study_name: str, channel_id: int):
    """스터디의 회의실 ID 설정"""
    _, members = read_study_file(study_name)
    write_study_file(study_name, channel_id, members)


def create_study(study_name: str, channel_id: int) -> bool:
    """새 스터디 생성 (회의실 ID 설정)"""
    filepath = get_study_file_path(study_name)
    
    # 이미 존재하는 경우
    if os.path.exists(filepath):
        return False
    
    # 빈 멤버 목록으로 파일 생성
    write_study_file(study_name, channel_id, {})
    return True


def delete_study(study_name: str) -> bool:
    """스터디 삭제"""
    filepath = get_study_file_path(study_name)
    
    # 파일이 없는 경우
    if not os.path.exists(filepath):
        return False
    
    # 파일 삭제
    os.remove(filepath)
    return True

