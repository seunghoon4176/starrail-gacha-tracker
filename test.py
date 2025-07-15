import pandas as pd
import asyncio
from GachaAPI import GachaAPI

# 테스트용 인증 링크 (실제 유효한 링크로 교체 필요)
gacha_link = ""

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
