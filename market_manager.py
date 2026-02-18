# market_manager.py - 마켓 파일 관리

import os
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path


MARKET_DIR = "market"

# 파일별 락 관리 (동시 구매 방지)
_file_locks: Dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


class MarketItem:
    """마켓 아이템 데이터 클래스"""
    def __init__(self, name: str, code: str, draw_count: int, max_purchase: int,
                 price_per_ticket: int, quantity: int, tickets_sold: int, buyers: List[str],
                 is_role: bool = False, role_name: str = None):
        self.name = name
        self.code = code
        self.draw_count = draw_count  # 뽑는 인원 수 (구매된 티켓들 중 뽑을 개수)
        self.max_purchase = max_purchase  # 구매 가능 수 (한 사람당 최대 구매 가능)
        self.price_per_ticket = price_per_ticket  # 티켓 당 가격 (역할의 경우 역할 가격)
        self.quantity = quantity  # 총 티켓 수량 (None이면 무제한)
        self.tickets_sold = tickets_sold  # 티켓 발행 수
        self.buyers = buyers  # 구매한 플레이어 명단 리스트
        self.is_role = is_role  # 역할 아이템인지 여부
        self.role_name = role_name  # 역할 이름 (역할 아이템인 경우)

    def get_user_ticket_count(self, user_name: str) -> int:
        """사용자가 구매한 티켓 수 반환"""
        return sum(1 for buyer in self.buyers if buyer == user_name)

    def can_purchase(self, user_name: str) -> bool:
        """사용자가 구매 가능한지 확인"""
        if self.is_role:
            # 역할은 이미 가지고 있으면 구매 불가
            return user_name not in self.buyers
        user_tickets = self.get_user_ticket_count(user_name)
        return user_tickets < self.max_purchase

    def is_available(self) -> bool:
        """아이템이 구매 가능한지 확인 (수량 체크)"""
        # quantity가 0이면 무제한
        if self.quantity == 0:
            return True
        return self.tickets_sold < self.quantity


def ensure_market_dir():
    """market 폴더가 없으면 생성"""
    Path(MARKET_DIR).mkdir(exist_ok=True)


def get_market_files() -> List[str]:
    """마켓 파일 목록 반환 (market.txt)"""
    ensure_market_dir()
    files = []
    market_file = "market.txt"
    filepath = os.path.join(MARKET_DIR, market_file)
    if os.path.exists(filepath):
        files.append(market_file)
    return files


def parse_market_file(filename: str) -> List[MarketItem]:
    """마켓 파일을 파싱하여 MarketItem 리스트 반환"""
    filepath = os.path.join(MARKET_DIR, filename)

    if not os.path.exists(filepath):
        return []

    items = []
    current_item = None
    current_buyers = []

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 빈 줄 스킵
        if not line:
            i += 1
            continue

        # 물품 헤더 파싱: # [물품 이름] : [물품 코드]([길이])
        if line.startswith('#'):
            # 이전 아이템 저장
            if current_item is not None:
                current_item.buyers = current_buyers
                items.append(current_item)
                current_buyers = []

            # 새 아이템 시작
            role_match = re.match(r'#\s*역할\s*:\s*(.+?)\s*:\s*(\S+)(?:\([^)]+\))?', line, re.IGNORECASE)
            if role_match:
                role_name = role_match.group(1).strip()
                code = role_match.group(2).strip()
                name = f"역할: {role_name}"

                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    price_match = re.match(r'p\s*:\s*(\d+)', next_line, re.IGNORECASE)
                    price_per_ticket = int(price_match.group(1)) if price_match else 0
                    tickets_sold = 0
                    if i + 2 < len(lines):
                        tickets_match = re.match(r'(\d+)', lines[i + 2].strip())
                        tickets_sold = int(tickets_match.group(1)) if tickets_match else 0

                    current_item = MarketItem(
                        name=name, code=code, draw_count=1, max_purchase=1,
                        price_per_ticket=price_per_ticket, quantity=0, tickets_sold=tickets_sold,
                        buyers=[], is_role=True, role_name=role_name
                    )
                    i += 3
                else:
                    i += 1
            else:
                match = re.match(r'#\s*(.+?)\s*:\s*(\S+)(?:\([^)]+\))?', line)
                if match:
                    name = match.group(1).strip()
                    code = match.group(2).strip()

                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        dp_match = re.match(r'(\d+)\s*:\s*(\d+)', next_line)
                        draw_count = int(dp_match.group(1)) if dp_match else 1
                        max_purchase = int(dp_match.group(2)) if dp_match else 1

                        price_per_ticket = 0
                        if i + 2 < len(lines):
                            price_match = re.match(r'p\s*:\s*(\d+)', lines[i + 2].strip(), re.IGNORECASE)
                            price_per_ticket = int(price_match.group(1)) if price_match else 0
                        tickets_sold = 0
                        if i + 3 < len(lines):
                            tickets_match = re.match(r'(\d+)', lines[i + 3].strip())
                            tickets_sold = int(tickets_match.group(1)) if tickets_match else 0
                        quantity = 0

                        current_item = MarketItem(
                            name=name, code=code, draw_count=draw_count, max_purchase=max_purchase,
                            price_per_ticket=price_per_ticket, quantity=quantity, tickets_sold=tickets_sold,
                            buyers=[], is_role=False, role_name=None
                        )
                        i += 4
                    else:
                        i += 1
                else:
                    i += 1

        elif line.startswith('@'):
            if current_item is not None:
                buyer_name = line[1:].strip()
                if buyer_name:
                    current_buyers.append(buyer_name)
            i += 1
        else:
            i += 1

    if current_item is not None:
        current_item.buyers = current_buyers
        items.append(current_item)

    return items


def save_market_file(filename: str, items: List[MarketItem]):
    """마켓 파일 저장"""
    ensure_market_dir()
    filepath = os.path.join(MARKET_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        for item in items:
            f.write(f"# {item.name} : {item.code}\n")
            if item.is_role:
                f.write(f"p : {item.price_per_ticket}\n")
                f.write(f"{item.tickets_sold}\n")
            else:
                f.write(f"{item.draw_count} : {item.max_purchase}\n")
                f.write(f"p : {item.price_per_ticket}\n")
                f.write(f"{item.tickets_sold}\n")
            for buyer in item.buyers:
                f.write(f"@{buyer}\n")
            f.write("\n")


def get_all_market_items() -> Dict[str, List[MarketItem]]:
    """모든 마켓 파일의 아이템을 반환 {filename: [items]}"""
    files = get_market_files()
    all_items = {}
    for filename in files:
        items = parse_market_file(filename)
        if items:
            all_items[filename] = items
    return all_items


def find_item_by_code(code: str) -> Optional[Tuple[str, MarketItem]]:
    """물품 코드로 아이템 찾기 (filename, item) 반환"""
    all_items = get_all_market_items()
    for filename, items in all_items.items():
        for item in items:
            if item.code.lower() == code.lower():
                return (filename, item)
    return None


async def get_file_lock(filename: str) -> asyncio.Lock:
    """파일별 락 가져오기 (없으면 생성)"""
    async with _locks_lock:
        if filename not in _file_locks:
            _file_locks[filename] = asyncio.Lock()
        return _file_locks[filename]


def purchase_ticket(filename: str, item_code: str, user_name: str) -> bool:
    """티켓 구매 처리 (파일 업데이트) - 동기 함수 (락은 호출 전에 획득해야 함)"""
    items = parse_market_file(filename)
    item = None
    for i in items:
        if i.code.lower() == item_code.lower():
            item = i
            break
    if item is None:
        return False
    item.tickets_sold += 1
    item.buyers.append(user_name)
    save_market_file(filename, items)
    return True


def get_user_purchase_history(user_name: str) -> List[Tuple[str, MarketItem, int]]:
    """특정 사용자의 구매 내역 조회. Returns: [(filename, item, ticket_count), ...]"""
    all_items = get_all_market_items()
    user_purchases = []
    for filename, items in all_items.items():
        for item in items:
            ticket_count = item.get_user_ticket_count(user_name)
            if ticket_count > 0:
                user_purchases.append((filename, item, ticket_count))
    return user_purchases


def add_market_item(filename: str, item: MarketItem) -> bool:
    """마켓에 아이템 추가"""
    items = parse_market_file(filename)
    for existing_item in items:
        if existing_item.code.lower() == item.code.lower():
            return False
    items.append(item)
    save_market_file(filename, items)
    return True


def clear_market_file(filename: str) -> bool:
    """마켓 파일 내용 모두 비우기"""
    filepath = os.path.join(MARKET_DIR, filename)
    if not os.path.exists(filepath):
        return False
    with open(filepath, 'w', encoding='utf-8') as f:
        pass
    return True


def remove_market_item(filename: str, item_code: str) -> bool:
    """마켓에서 아이템 제거"""
    items = parse_market_file(filename)
    removed = False
    for i, item in enumerate(items):
        if item.code.lower() == item_code.lower():
            items.pop(i)
            removed = True
            break
    if not removed:
        return False
    save_market_file(filename, items)
    return True
