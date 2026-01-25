# level_ranges_manager.py - 레벨 범위 설정 파일 관리

import os
from typing import Dict, Tuple, Optional
from pathlib import Path

LEVEL_RANGES_FILE = "level_ranges.txt"


def ensure_file():
    """파일이 없으면 생성하고 config.py의 기본값으로 초기화"""
    if not os.path.exists(LEVEL_RANGES_FILE):
        # config.py에서 기본값 로드
        try:
            from config import _DEFAULT_LEVEL_RANGES as default_ranges
        except ImportError:
            # _DEFAULT_LEVEL_RANGES가 없으면 빈 딕셔너리 사용
            default_ranges = {}
        
        # 재귀 호출 없이 직접 파일에 쓰기
        try:
            with open(LEVEL_RANGES_FILE, 'w', encoding='utf-8') as f:
                # 시작 레벨 순으로 정렬
                for (start, end), (minutes, points) in sorted(default_ranges.items(), key=lambda x: x[0][0]):
                    f.write(f"{start}~{end}:{minutes}:{points}\n")
        except Exception as e:
            print(f"[LevelRangesManager] 파일 초기화 오류: {e}")


def load_level_ranges() -> Dict[Tuple[int, int], Tuple[int, int]]:
    """
    level_ranges.txt 파일에서 설정 로드
    Returns: {(시작레벨, 끝레벨): (레벨업_시간_분, 레벨업_포인트)}
    """
    ensure_file()
    
    result = {}
    
    if not os.path.exists(LEVEL_RANGES_FILE):
        return result
    
    try:
        with open(LEVEL_RANGES_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 형식: start~end:minutes:points
                # 예: 1~10:10:10
                if ':' in line and '~' in line:
                    # 범위와 값 분리
                    if line.count(':') >= 2:
                        range_part, minutes, points = line.split(':', 2)
                        if '~' in range_part:
                            start_str, end_str = range_part.split('~', 1)
                            try:
                                start = int(start_str.strip())
                                end = int(end_str.strip())
                                minutes_val = int(minutes.strip())
                                points_val = int(points.strip())
                                
                                if start > end:
                                    continue
                                
                                result[(start, end)] = (minutes_val, points_val)
                            except ValueError:
                                continue
    except Exception as e:
        print(f"[LevelRangesManager] 파일 읽기 오류: {e}")
    
    return result


def save_level_ranges(level_ranges: Dict[Tuple[int, int], Tuple[int, int]]):
    """
    level_ranges.txt 파일에 설정 저장
    Args:
        level_ranges: {(시작레벨, 끝레벨): (레벨업_시간_분, 레벨업_포인트)}
    """
    # 파일이 없으면 기본값으로 초기화 (재귀 호출 방지를 위해 직접 확인)
    if not os.path.exists(LEVEL_RANGES_FILE):
        ensure_file()
    
    try:
        with open(LEVEL_RANGES_FILE, 'w', encoding='utf-8') as f:
            # 시작 레벨 순으로 정렬
            for (start, end), (minutes, points) in sorted(level_ranges.items(), key=lambda x: x[0][0]):
                f.write(f"{start}~{end}:{minutes}:{points}\n")
    except Exception as e:
        print(f"[LevelRangesManager] 파일 쓰기 오류: {e}")
        raise


def add_level_range(start: int, end: int, minutes: int, points: int) -> bool:
    """
    레벨 범위 설정 추가
    Returns: 성공 여부
    """
    if start > end:
        return False
    
    ranges = load_level_ranges()
    ranges[(start, end)] = (minutes, points)
    save_level_ranges(ranges)
    return True


def remove_level_ranges_by_range(target_start: int, target_end: int) -> list:
    """
    지정된 범위와 겹치는 모든 레벨 범위 제거
    Args:
        target_start: 제거할 범위의 시작 레벨
        target_end: 제거할 범위의 끝 레벨
    Returns: 삭제된 범위들의 리스트 [(시작, 끝, 분, 포인트), ...]
    """
    if target_start > target_end:
        return []
    
    ranges = load_level_ranges()
    removed = []
    
    # 겹치는 범위 찾기
    to_remove = []
    for (start, end), (minutes, points) in ranges.items():
        # 범위가 겹치는지 확인
        # 겹치는 조건: (start <= target_end) and (end >= target_start)
        if start <= target_end and end >= target_start:
            to_remove.append((start, end))
            removed.append((start, end, minutes, points))
    
    # 제거
    for key in to_remove:
        del ranges[key]
    
    if removed:
        save_level_ranges(ranges)
    
    return removed


def update_level_range(start: int, end: int, minutes: int, points: int) -> bool:
    """
    레벨 범위 설정 업데이트 (기존 범위와 겹치면 교체)
    겹치는 기존 범위들을 제거하고 새 범위 추가
    Returns: 성공 여부
    """
    if start > end:
        return False
    
    # 겹치는 범위 제거
    remove_level_ranges_by_range(start, end)
    
    # 새 범위 추가
    return add_level_range(start, end, minutes, points)


def get_level_range(level: int) -> Optional[Tuple[int, int]]:
    """
    특정 레벨에 해당하는 범위 정보 조회
    Returns: (레벨업_시간_분, 레벨업_포인트) 또는 None
    """
    ranges = load_level_ranges()
    
    for (start, end), (minutes, points) in ranges.items():
        if start <= level <= end:
            return (minutes, points)
    
    return None

