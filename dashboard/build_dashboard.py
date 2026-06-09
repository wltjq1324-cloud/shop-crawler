#!/usr/bin/env python3
"""data/shop.db 의 최신 수집 결과로 쇼핑몰 스타일 대시보드(HTML)를 생성한다.

- 플랫폼 채널별 탭: G마켓 신선 / G마켓 가공 / GS샵 / 카카오 톡딜 / NS몰
  (NS몰 탭은 농산 1~10 → 수산 1~10 → 축산 1~10 순서로 한 탭에 묶음)
- 상품 카드 그리드: 썸네일 + 상품명 + 정가(취소선) + 할인율% + 판매가
  데스크톱 한 행 5개 × 6줄(30개), 화면 폭에 따라 4/3/2열 반응형(모바일 대응)
- 탭은 CSS 라디오 방식이라 JS 없이도 동작. 외부 CDN 불필요(완전 자급자족 HTML).

사용: python dashboard/build_dashboard.py [--db ...] [--out ...] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import html
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 탭 구성: NS몰은 농산→수산→축산 순서로 한 탭에 통합
TABS = [
    {"id": "gmf", "label": "G마켓 신선", "targets": ["gmarket_fresh"]},
    {"id": "gmp", "label": "G마켓 가공", "targets": ["gmarket_processed"]},
    {"id": "gss", "label": "GS샵", "targets": ["gsshop_best"]},
    {"id": "ktd", "label": "카카오 톡딜", "targets": ["kakao_talkdeal_food"]},
    {"id": "nsm", "label": "NS몰",
     "targets": ["nsmall_nongsan", "nsmall_susan", "nsmall_chuksan"],
     "cats": {"nsmall_nongsan": "농산", "nsmall_susan": "수산", "nsmall_chuksan": "축산"}},
]

QTY_LABEL = {"kakao_talkdeal_food": "주문"}  # 그 외 sales_qty 보유 타겟은 '구매'


def esc(v: object) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def won(v: object) -> str:
    return f"{int(v):,}원" if v not in (None, "") else ""


def latest_date(conn: sqlite3.Connection, override: str | None) -> str | None:
    if override:
        return override
    row = conn.execute("SELECT MAX(run_date) FROM crawl_runs").fetchone()
    return row[0] if row else None


def latest_run(conn: sqlite3.Connection, target_key: str, run_date: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM crawl_runs
        WHERE target_key=? AND run_date=?
        ORDER BY run_at DESC LIMIT 1
        """,
        (target_key, run_date),
    ).fetchone()


def ranks_for(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM product_ranks WHERE run_id=? ORDER BY rank", (run_id,)
    ).fetchall()


def card_html(r: sqlite3.Row, qty_label: str, cat: str | None) -> str:
    name = r["product_name"] or "(이름 없음)"
    img = (
        f'<img src="{esc(r["image_url"])}" alt="{esc(name)}" loading="lazy">'
        if r["image_url"] else '<div class="noimg">🛒</div>'
    )
    rk = f'<span class="rk">{esc(r["rank"])}</span>'
    ad = '<span class="bdg-ad">AD</span>' if r["is_ad"] else ""
    so = '<div class="so"><span>품절</span></div>' if r["is_sold_out"] else ""
    cat_h = f'<span class="cat">{esc(cat)}</span>' if cat else ""

    has_dc = bool(r["list_price"] and r["sale_price"] and r["list_price"] > r["sale_price"])
    orig = f'<p class="orig"><s>나의 할인가 {won(r["list_price"])}</s></p>' if has_dc else '<p class="orig">&nbsp;</p>'
    dc = f'<b class="dc">{esc(r["discount_rate"])}%</b>' if (has_dc and r["discount_rate"]) else ""
    price = f'<p class="prc">{dc}<b class="val">{won(r["sale_price"]) or "-"}</b></p>'

    meta_bits = []
    if r["rating"]:
        meta_bits.append(f'★ {esc(r["rating"])}')
    if r["review_count"]:
        meta_bits.append(f'리뷰 {int(r["review_count"]):,}')
    if r["sales_qty"]:
        meta_bits.append(f'{qty_label} {int(r["sales_qty"]):,}')
    meta = f'<p class="meta">{" · ".join(meta_bits)}</p>' if meta_bits else '<p class="meta">&nbsp;</p>'

    href = esc(r["product_url"] or "#")
    return (
        f'<a class="card" href="{href}" target="_blank" rel="noopener">'
        f'<div class="thumb">{rk}{img}{ad}{so}</div>'
        f'<div class="info">{cat_h}<p class="nm">{esc(name)}</p>{orig}{price}{meta}</div>'
        f'</a>'
    )


def build(db_path: Path, out_path: Path, date_override: str | None) -> Path:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    run_date = latest_date(conn, date_override)

    inputs, labels, panels = [], [], []
    for i, tab in enumerate(TABS):
        checked = " checked" if i == 0 else ""
        inputs.append(f'<input type="radio" name="tab" id="t-{tab["id"]}"{checked}>')
        labels.append(f'<label for="t-{tab["id"]}">{esc(tab["label"])}</label>')

        cards, meta_chips, total = [], [], 0
        for tk in tab["targets"]:
            run = latest_run(conn, tk, run_date) if run_date else None
            if not run:
                continue
            cat = (tab.get("cats") or {}).get(tk)
            qty_label = QTY_LABEL.get(tk, "구매")
            rows = ranks_for(conn, run["id"])
            total += len(rows)
            meta_chips.append(f'<span class="chip">⏰ {esc(run["schedule"])} 수집</span>')
            for r in rows:
                cards.append(card_html(r, qty_label, cat))
        # 탭당 수집시각 chip 은 중복 제거
        chips = "".join(dict.fromkeys(meta_chips))
        body = (
            f'<div class="grid">{"".join(cards)}</div>'
            if cards else '<div class="empty">이 채널의 수집 데이터가 없습니다.</div>'
        )
        panels.append(
            f'<section class="panel" id="p-{tab["id"]}">'
            f'<div class="phead"><h2>{esc(tab["label"])} <em>TOP {total}</em></h2><div>{chips}</div></div>'
            f'{body}</section>'
        )

    conn.close()

    # 탭 표시/활성 CSS 는 id 조합으로 생성
    css_rules = []
    for tab in TABS:
        css_rules.append(f'#t-{tab["id"]}:checked ~ #p-{tab["id"]}{{display:block}}')
        css_rules.append(
            f'#t-{tab["id"]}:checked ~ .tabbar label[for="t-{tab["id"]}"]'
            "{background:#111;color:#fff;border-color:#111}"
        )

    doc = (
        HTML_TEMPLATE
        .replace("__DATE__", esc(run_date or "데이터 없음"))
        .replace("__TAB_CSS__", "\n".join(css_rules))
        .replace("__INPUTS__", "".join(inputs))
        .replace("__LABELS__", "".join(labels))
        .replace("__PANELS__", "".join(panels))
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


HTML_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>쇼핑몰 베스트 랭킹</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#fff;color:#111;
  font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:20px 16px 60px}
header h1{font-size:22px;margin:0 0 2px;letter-spacing:-.3px}
header .sub{color:#888;font-size:13px;margin-bottom:14px}
input[name=tab]{position:absolute;opacity:0;pointer-events:none}
.tabbar{display:flex;gap:8px;overflow-x:auto;padding:4px 0 14px;position:sticky;top:0;
  background:#fff;z-index:10;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabbar::-webkit-scrollbar{display:none}
.tabbar label{flex:0 0 auto;padding:8px 16px;border:1px solid #ddd;border-radius:22px;
  font-size:14px;font-weight:600;color:#333;cursor:pointer;white-space:nowrap;background:#fff}
.panel{display:none}
__TAB_CSS__
.phead{display:flex;justify-content:space-between;align-items:center;gap:8px;
  margin:6px 0 14px;flex-wrap:wrap}
.phead h2{font-size:17px;margin:0}
.phead em{font-style:normal;color:#e8453c;font-size:14px}
.chip{font-size:12px;color:#777;background:#f5f5f5;border-radius:14px;padding:4px 10px}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:22px 14px}
@media(max-width:1024px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:820px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:560px){.grid{grid-template-columns:repeat(2,1fr);gap:18px 10px}}
.card{display:block;text-decoration:none;color:inherit}
.thumb{position:relative;aspect-ratio:1/1;border-radius:10px;overflow:hidden;
  background:#f6f6f6;border:1px solid #eee}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.noimg{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:44px}
.rk{position:absolute;top:0;left:0;background:rgba(17,17,17,.85);color:#fff;font-size:12px;
  font-weight:700;min-width:24px;height:24px;display:flex;align-items:center;justify-content:center;
  border-radius:0 0 8px 0;z-index:2;padding:0 6px}
.bdg-ad{position:absolute;bottom:6px;left:6px;background:rgba(255,255,255,.92);border:1px solid #ccc;
  color:#666;font-size:10px;font-weight:700;padding:1px 5px;border-radius:4px;z-index:2}
.so{position:absolute;inset:0;background:rgba(255,255,255,.65);display:flex;align-items:center;
  justify-content:center;z-index:3}
.so span{background:rgba(17,17,17,.8);color:#fff;font-size:13px;font-weight:700;
  padding:6px 14px;border-radius:18px}
.info{padding:8px 2px 0}
.cat{display:inline-block;font-size:11px;font-weight:700;color:#0a7;background:#e9faf3;
  border-radius:4px;padding:1px 6px;margin-bottom:3px}
.nm{margin:0;font-size:13px;line-height:1.4;color:#222;height:2.8em;overflow:hidden;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.orig{margin:4px 0 0;font-size:11px;color:#aaa;min-height:13px}
.orig s{color:#aaa}
.prc{margin:2px 0 0;display:flex;align-items:baseline;gap:5px}
.dc{color:#e8453c;font-size:15px;font-weight:800}
.val{font-size:15px;font-weight:800;color:#111}
.meta{margin:4px 0 0;font-size:11px;color:#999;min-height:13px}
.empty{color:#999;padding:48px 0;text-align:center;border:1px dashed #ddd;border-radius:12px}
footer{color:#bbb;font-size:11px;text-align:center;margin-top:40px}
</style></head>
<body><div class="wrap">
<header><h1>🛒 쇼핑몰 베스트 랭킹</h1>
<div class="sub">수집일자 __DATE__ · 채널 탭을 눌러 전환</div></header>
__INPUTS__
<nav class="tabbar">__LABELS__</nav>
__PANELS__
<footer>shop-crawler · crawl_runs / product_ranks 기반 정적 생성</footer>
</div></body></html>"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "shop.db"))
    ap.add_argument("--out", default=str(ROOT / "dashboard" / "index.html"))
    ap.add_argument("--date", default=None, help="특정 run_date (기본: 최신)")
    args = ap.parse_args(argv)
    out = build(Path(args.db), Path(args.out), args.date)
    print(f"대시보드 생성: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
