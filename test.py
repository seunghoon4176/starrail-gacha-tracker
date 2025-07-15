import pandas as pd
import asyncio
from GachaAPI import GachaAPI

# 테스트용 인증 링크 (실제 유효한 링크로 교체 필요)
gacha_link = "https://public-operation-hkrpg-sg.hoyoverse.com/common/gacha_record/api/getGachaLog?authkey_ver=1&sign_type=2&lang=ko&authkey=OG7TC5Uknceb425ZLMVkcyzhVfnH2rGWpjCTnqmYkG9Sk%2bqaO%2fpjsMAmKw%2fB2uIo3y0%2bdsfLRpnn3tq6qBvLeg1WX0vKpO5aOSpPZXasHs5SYeKOBl5InCYSiOIb%2b3K3ZcuHXAqMc7RcLpWTzKJNiPGjFGU5f6pPwJvvQ5sI6aaJ4wmLugR8ul6SG9jbM4m5jyLJfwjANV6%2fub7gY2VNsmvIbeyMXDuFFhSur0XoDCMmV%2baU37R6X2DmehIZxVtyg3GUAvo4fdXpY4Pv8Q6gof72Mw5gtUdQzLBOFA4%2bzyREiC9q%2bZFYOfitcWo3RV3RAy%2fpTBWQJEutbvYyZjWsFY%2fG0LvRZhqQH234tR71tCM%2f8fhB7XJhKWQjgozB8q694jOJrWIHq2UmRuztTl8gOG013tiNNW4uQ00jC9uAzqFz%2bbBFFFiBtAmwe58a%2fkcbvIq7CBq4ydczm9LgG5euRdtX2L3zbKr47qXAlHf0ML2kSE0zaJoFZezEGzObFhjg3VJK8k9wB%2f3ipZ%2f2eag%2fn%2bfJ0qq169Kvakwqs69l%2br4AZd7O%2bo8Z9tRUoNq5948GDJsqh0n%2fKfEGdxEK83n4jVWuUJXdJYYt5dnP7AzDccizuqNB5nf6eLPATq2Ml2xkAhYneJqdaTzS8yqlPO%2bVyZQnLQf%2fU1RQtbfEahjCMA8%3d&game_biz=hkrpg_global"

async def fetch_and_collect_all_items():
    api = GachaAPI(gacha_link)
    all_types = ["11", "12", "1", "2", "21", "22"]  # 모든 배너 타입
    item_set = set()
    for gacha_type in all_types:
        records = await api.fetch_gacha_records(gacha_type, "ko")
        for rec in records:
            item_id = rec.get("item_id")
            item_name = rec.get("name")
            if item_id and item_name:
                item_set.add((str(item_id), str(item_name)))
    # id 기준 정렬
    for item_id, item_name in sorted(item_set, key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
        print(f"{item_id},{item_name}")

if __name__ == "__main__":
    asyncio.run(fetch_and_collect_all_items())
