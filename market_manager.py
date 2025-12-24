# market_manager.py - 마켓 파일 관리

import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path


MARKET_DIR = "market"


class MarketItem:
    """마켓 아이템 데이터 클래스"""
    def __init__(self, name: str, code: str, draw_count: int, max_purchase: int, 
                 price_per_ticket: int, quantity: int, tickets_sold: int, buyers: List[str]):
        self.name = name
        self.code = code
        self.draw_count = draw_count  # 뽑는 인원 수 (구매된 티켓들 중 뽑을 개수)
        self.max_purchase = max_purchase  # 구매 가능 수 (한 사람당 최대 구매 가능)
        self.price_per_ticket = price_per_ticket  # 티켓 당 가격
        self.quantity = quantity  # 총 티켓 수량 (None이면 무제한)
        self.tickets_sold = tickets_sold  # 티켓 발행 수
        self.buyers = buyers  # 구매한 플레이어 명단 리스트
    
    def get_user_ticket_count(self, user_name: str) -> int:
        """사용자가 구매한 티켓 수 반환"""
        return sum(1 for buyer in self.buyers if buyer == user_name)
    
    def can_purchase(self, user_name: str) -> bool:
        """사용자가 구매 가능한지 확인"""
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
    """모든 마켓 파일 목록 반환 (YY_MM_market.txt 형식)"""
    ensure_market_dir()
    files = []
    for file in os.listdir(MARKET_DIR):
        if file.endswith("_market.txt"):
            files.append(file)
    return sorted(files, reverse=True)  # 최신 파일이 먼저 오도록


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
            
            # 새 아이템 시작: # 햄버거 상품권 : ASAV1231(8자리)
            # 형식: # [이름] : [코드]([길이])
            match = re.match(r'#\s*(.+?)\s*:\s*(\w+)(?:\([^)]+\))?', line)
            if match:
                name = match.group(1).strip()
                code = match.group(2).strip()
                
                # 다음 줄들 읽기
                if i + 1 < len(lines):
                    # [뽑는 인원 수] : [구매 가능 수]
                    draw_purchase_line = lines[i + 1].strip()
                    dp_match = re.match(r'(\d+)\s*:\s*(\d+)', draw_purchase_line)
                    if dp_match:
                        draw_count = int(dp_match.group(1))
                        max_purchase = int(dp_match.group(2))
                    else:
                        draw_count = 1
                        max_purchase = 1
                    
                    # p : [티켓 당 가격]
                    if i + 2 < len(lines):
                        price_line = lines[i + 2].strip()
                        price_match = re.match(r'p\s*:\s*(\d+)', price_line, re.IGNORECASE)
                        price_per_ticket = int(price_match.group(1)) if price_match else 0
                    else:
                        price_per_ticket = 0
                    
                    # [티켓 발행 수]
                    if i + 3 < len(lines):
                        tickets_line = lines[i + 3].strip()
                        tickets_match = re.match(r'(\d+)', tickets_line)
                        tickets_sold = int(tickets_match.group(1)) if tickets_match else 0
                    else:
                        tickets_sold = 0
                    
                    # quantity는 파일에 없으므로 무제한(0)으로 설정
                    quantity = 0
                    
                    current_item = MarketItem(
                        name=name,
                        code=code,
                        draw_count=draw_count,
                        max_purchase=max_purchase,
                        price_per_ticket=price_per_ticket,
                        quantity=quantity,
                        tickets_sold=tickets_sold,
                        buyers=[]
                    )
                    i += 4  # 헤더 + 3줄 건너뛰기
                else:
                    i += 1
            else:
                i += 1
        
        # 구매자 명단: @사용자 이름
        elif line.startswith('@'):
            if current_item is not None:
                # @ 뒤의 모든 내용을 사용자 이름으로 파싱
                buyer_name = line[1:].strip()  # @ 제거 후 공백 제거
                if buyer_name:  # 빈 문자열이 아닌 경우만 추가
                    current_buyers.append(buyer_name)
            i += 1
        else:
            i += 1
    
    # 마지막 아이템 저장
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
            # 헤더: # [물품 이름] : [물품 코드]
            f.write(f"# {item.name} : {item.code}\n")
            # [뽑는 인원 수] : [구매 가능 수]
            f.write(f"{item.draw_count} : {item.max_purchase}\n")
            # p : [티켓 당 가격]
            f.write(f"p : {item.price_per_ticket}\n")
            # [티켓 발행 수]
            f.write(f"{item.tickets_sold}\n")
            
            # 구매자 명단
            for buyer in item.buyers:
                f.write(f"@{buyer}\n")
            
            f.write("\n")  # 아이템 간 구분


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


def purchase_ticket(filename: str, item_code: str, user_name: str) -> bool:
    """티켓 구매 처리 (파일 업데이트)"""
    items = parse_market_file(filename)
    
    # 아이템 찾기
    item = None
    for i in items:
        if i.code.lower() == item_code.lower():
            item = i
            break
    
    if item is None:
        return False
    
    # 티켓 발행 수 증가
    item.tickets_sold += 1
    
    # 구매자 명단에 추가
    item.buyers.append(user_name)
    
    # 파일 저장
    save_market_file(filename, items)
    
    return True


def get_purchase_history() -> Dict[str, Dict[str, int]]:
    """
    구매 내역 조회
    Returns: {user_name: {item_code: ticket_count}}
    """
    all_items = get_all_market_items()
    history = {}
    
    for filename, items in all_items.items():
        for item in items:
            for buyer in item.buyers:
                if buyer not in history:
                    history[buyer] = {}
                if item.code not in history[buyer]:
                    history[buyer][item.code] = 0
                history[buyer][item.code] += 1
    
    return history


def get_user_purchase_history(user_name: str) -> List[Tuple[str, MarketItem, int]]:
    """
    특정 사용자의 구매 내역 조회
    Returns: [(filename, item, ticket_count), ...]
    """
    all_items = get_all_market_items()
    user_purchases = []
    
    for filename, items in all_items.items():
        for item in items:
            ticket_count = item.get_user_ticket_count(user_name)
            if ticket_count > 0:
                user_purchases.append((filename, item, ticket_count))
    
    return user_purchases


def get_item_purchase_summary() -> Dict[str, Dict[str, int]]:
    """
    물품별 구매 내역 조회
    Returns: {item_code: {user_name: ticket_count}}
    """
    all_items = get_all_market_items()
    item_summary = {}
    
    for filename, items in all_items.items():
        for item in items:
            if item.code not in item_summary:
                item_summary[item.code] = {}
            
            # 구매자별 티켓 수 계산
            for buyer in item.buyers:
                if buyer not in item_summary[item.code]:
                    item_summary[item.code][buyer] = 0
                item_summary[item.code][buyer] += 1
    
    return item_summary

