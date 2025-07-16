# hakushin-py 라이브러리를 사용해 https://hsr20.hakush.in 의 캐릭터 데이터를 파싱하는 예제입니다.
# pip install hakushin-py 필요
import hakushin
import asyncio

async def main() -> None:
    async with hakushin.HakushinAPI(hakushin.Game.HSR, hakushin.Language.KO) as client:
        await client.fetch_characters()
    async with hakushin.HakushinAPI(hakushin.Game.HSR, hakushin.Language.KO) as client:
        await client.fetch_light_cones()

asyncio.run(main())
