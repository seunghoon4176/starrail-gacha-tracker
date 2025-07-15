import asyncio
from GachaAPI import GachaAPI

async def export_gacha_items(gacha_link, output_path="gacha_items.txt"):
    api = GachaAPI(gacha_link)
    all_types = ["11", "12", "1", "2", "21", "22"]
    item_set = set()
    for gacha_type in all_types:
        records = await api.fetch_gacha_records(gacha_type, "ko")
        for rec in records:
            item_id = rec.get("item_id")
            item_name = rec.get("name")
            if item_id and item_name:
                item_set.add((str(item_id), str(item_name)))
    with open(output_path, "w", encoding="utf-8") as f:
        for item_id, item_name in sorted(item_set, key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
            f.write(f"{item_id},{item_name}\n")
    print(f"아이템 목록이 {output_path} 파일로 저장되었습니다.")

if __name__ == "__main__":
    gacha_link = input("가챠 링크를 붙여넣으세요: ").strip()
    asyncio.run(export_gacha_items(gacha_link))
