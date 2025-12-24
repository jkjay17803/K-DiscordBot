# market.py - 마켓 구매 내역 조회 스크립트

from market_manager import get_item_purchase_summary, get_all_market_items


def show_purchase_history():
    """구매 내역 표시 (물품별)"""
    item_summary = get_item_purchase_summary()
    
    if not item_summary:
        print("구매 내역이 없습니다.")
        return
    
    print("=" * 80)
    print("구매 내역 (물품별)")
    print("=" * 80)
    
    # 아이템 정보 가져오기
    all_items = get_all_market_items()
    item_info = {}  # {item_code: item_name}
    
    for filename, items in all_items.items():
        for item in items:
            if item.code not in item_info:
                item_info[item.code] = item.name
    
    # 물품 코드로 정렬
    sorted_items = sorted(item_summary.items(), key=lambda x: x[0])
    
    for item_code, buyers in sorted_items:
        item_name = item_info.get(item_code, "알 수 없음")
        print(f"\n[{item_name}] ({item_code})")
        print("-" * 80)
        
        # 사용자별로 정렬
        sorted_buyers = sorted(buyers.items(), key=lambda x: x[0])
        
        for user_name, ticket_count in sorted_buyers:
            print(f"  - @{user_name} {ticket_count}개")
    
    print("\n" + "=" * 80)


def main():
    """메인 함수"""
    while True:
        print("\n" + "=" * 80)
        print("마켓 관리 시스템")
        print("=" * 80)
        print("0. 종료")
        print("1. 구매 내역 조회")
        print("=" * 80)
        
        try:
            choice = input("\n선택: ").strip()
            
            if choice == "0":
                print("프로그램을 종료합니다.")
                break
            elif choice == "1":
                show_purchase_history()
            else:
                print("❌ 잘못된 선택입니다. 0 또는 1을 입력해주세요.")
        
        except KeyboardInterrupt:
            print("\n\n프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()

