#!/usr/bin/env python3
"""대시보드 데모용 샘플 데이터 시드.

실제 크롤링 전에 대시보드를 확인할 수 있도록 targets.yaml 의 각 타겟에 대해
그럴듯한 순위 데이터를 생성해 data/shop.db 에 넣는다. (실데이터가 쌓이면 그대로
함께 조회된다.) 멱등성을 위해 같은 run_date 의 기존 샘플 run 은 지우고 다시 넣는다.
"""

from __future__ import annotations

import datetime as dt
import random
import sys
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler import db as dbmod  # noqa: E402
from crawler.config import ROOT, load_targets  # noqa: E402
from crawler.exporter import export_csv  # noqa: E402
from crawler.models import ProductRank  # noqa: E402

random.seed(42)

NAMES = {
    "gmarket_fresh": ["충주 사과 {n}kg", "제주 감귤 {n}kg", "성주 참외 {n}kg", "고당도 샤인머스캣 {n}송이",
                       "친환경 바나나 {n}kg", "햇 양파 {n}kg", "国産 대추방울토마토 {n}kg", "블루베리 {n}g"],
    "gmarket_processed": ["오뚜기 진라면 {n}개입", "햇반 {n}개", "스팸 클래식 {n}호", "비비고 만두 {n}봉",
                          "코카콜라 {n}ml x24", "농심 신라면 {n}개입", "곰표 밀가루 {n}kg", "참치캔 {n}호"],
    "gsshop_best": ["프리미엄 한우 등심 {n}g", "랍스터테일 {n}미", "전복 {n}미", "킹크랩 {n}kg",
                    "갈치 {n}손", "명품 굴비 {n}미", "황태채 {n}g", "수제 떡갈비 {n}개"],
    "kakao_talkdeal_food": ["[톡딜] 닭가슴살 {n}팩", "[톡딜] 곤약젤리 {n}개", "[톡딜] 아메리카노 {n}스틱",
                            "[톡딜] 견과류 {n}봉", "[톡딜] 단백질바 {n}개", "[톡딜] 누룽지 {n}g",
                            "[톡딜] 곤드레밥 {n}인분", "[톡딜] 떡볶이 {n}인분"],
    "nsmall_nongsan": ["해남 꿀고구마 {n}kg", "유기농 쌀 {n}kg", "곰탕용 표고버섯 {n}g", "햇 밤 {n}kg"],
    "nsmall_susan": ["완도 전복 {n}미", "제주 갈치 {n}손", "통영 굴 {n}kg", "노르웨이 고등어 {n}손"],
    "nsmall_chuksan": ["1++ 한우 불고기 {n}g", "이베리코 목살 {n}g", "토종닭 {n}호", "양념 LA갈비 {n}g"],
}


# 상품명 키워드 → 썸네일 이모지
EMOJI = [("사과", "🍎"), ("감귤", "🍊"), ("참외", "🍈"), ("머스캣", "🍇"), ("바나나", "🍌"),
         ("양파", "🧅"), ("토마토", "🍅"), ("블루베리", "🫐"), ("라면", "🍜"), ("햇반", "🍚"),
         ("스팸", "🥫"), ("만두", "🥟"), ("콜라", "🥤"), ("밀가루", "🌾"), ("참치", "🐟"),
         ("한우", "🥩"), ("랍스터", "🦞"), ("전복", "🐚"), ("킹크랩", "🦀"), ("갈치", "🐟"),
         ("굴비", "🐟"), ("황태", "🐟"), ("떡갈비", "🍖"), ("닭가슴살", "🍗"), ("젤리", "🍬"),
         ("아메리카노", "☕"), ("견과", "🥜"), ("단백질바", "🍫"), ("누룽지", "🍘"), ("곤드레", "🍚"),
         ("떡볶이", "🍢"), ("고구마", "🍠"), ("쌀", "🌾"), ("버섯", "🍄"), ("밤", "🌰"),
         ("고등어", "🐟"), ("목살", "🥓"), ("토종닭", "🐔"), ("갈비", "🍖"), ("굴", "🦪")]
PALETTES = [("#fde8e8", "#f8b4b4"), ("#e8f3fd", "#a9d0f5"), ("#eafde8", "#b4e8ae"),
            ("#fdf6e8", "#f5d9a9"), ("#f3e8fd", "#d4b4f8"), ("#e8fdf8", "#a9f5dd")]


def thumb_uri(name: str, rank: int) -> str:
    """상품명 기반 placeholder 썸네일(SVG data URI). 오프라인에서도 렌더된다."""
    emoji = next((e for kw, e in EMOJI if kw in name), "🛒")
    c1, c2 = PALETTES[rank % len(PALETTES)]
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
        f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop offset='0' stop-color='{c1}'/><stop offset='1' stop-color='{c2}'/>"
        f"</linearGradient></defs>"
        f"<rect width='300' height='300' fill='url(#g)'/>"
        f"<text x='150' y='160' font-size='110' text-anchor='middle'>{emoji}</text></svg>"
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def gen_rows(key: str, top_n: int, sales_qty_source: str | None) -> list[ProductRank]:
    names = NAMES.get(key, ["상품 {n}"])
    rows: list[ProductRank] = []
    for rank in range(1, top_n + 1):
        base = names[(rank - 1) % len(names)].format(n=random.choice([1, 2, 3, 5, 10, 500, 1000]))
        list_price = random.choice([9900, 12900, 19900, 25000, 39000, 49900, 79000, 120000])
        rate = random.choice([0, 0, 5, 10, 15, 20, 25, 30, 40, 50])
        sale_price = int(round(list_price * (100 - rate) / 100 / 10) * 10)
        sold_out = random.random() < 0.07
        is_ad = rank <= 2 and random.random() < 0.5
        sales_qty = None
        if sales_qty_source:
            # 상위권일수록 판매량 ↑
            sales_qty = int(random.randint(50, 500) * (top_n - rank + 1) / 2)
        rows.append(
            ProductRank(
                rank=rank,
                product_name=base,
                product_id=f"{key[:3]}{1000 + rank}",
                list_price=list_price,
                sale_price=sale_price,
                discount_rate=rate or None,
                sales_qty=sales_qty,
                order_count=sales_qty,
                review_count=random.randint(0, 5000),
                rating=round(random.uniform(3.8, 5.0), 1),
                is_sold_out=sold_out,
                is_ad=is_ad,
                product_url=f"https://example.com/{key}/{1000 + rank}",
                image_url=thumb_uri(base, rank),
            )
        )
    return rows


def main() -> int:
    targets = load_targets()
    kst = ZoneInfo("Asia/Seoul")
    now = dt.datetime.now(kst)
    run_date = now.strftime("%Y-%m-%d")

    db_path = ROOT / "data" / "shop.db"
    conn = dbmod.connect(db_path)
    dbmod.init_db(conn)

    # 같은 날짜 기존 데이터 정리(샘플 재실행 멱등)
    conn.execute(
        "DELETE FROM product_ranks WHERE run_id IN (SELECT id FROM crawl_runs WHERE run_date=?)",
        (run_date,),
    )
    conn.execute("DELETE FROM crawl_runs WHERE run_date=?", (run_date,))
    conn.commit()

    exports_dir = ROOT / "exports"
    for t in targets:
        rows = gen_rows(t.key, t.top_n, t.sales_qty_source)
        run_at = now.replace(hour=int(t.schedule.split(":")[0]), minute=int(t.schedule.split(":")[1]))
        run_id = dbmod.start_run(
            conn, target_key=t.key, label=t.label, url=t.url, run_date=run_date,
            run_at=run_at, schedule=t.schedule, top_n=t.top_n,
        )
        dbmod.insert_ranks(conn, run_id, t.key, run_date, rows)
        csv_path = exports_dir / f"{run_date}_{t.key}.csv"
        export_csv(rows, csv_path)
        dbmod.finish_run(
            conn, run_id, status="success", item_count=len(rows),
            screenshot_path=f"screenshots/{run_date}/{t.key}.png", csv_path=str(csv_path),
        )
        print(f"  seeded {t.key:22s} {len(rows)}건")

    conn.close()
    print(f"\n샘플 데이터 시드 완료: {db_path}  (run_date={run_date})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
