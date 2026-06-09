#!/usr/bin/env python3
"""data/shop.db 의 최신 수집 결과로 정적 대시보드(HTML)를 생성한다.

외부 CDN/JS 없이 인라인 CSS + SVG 막대만 사용하므로 오프라인에서도 그대로 렌더된다.
사용: python dashboard/build_dashboard.py [--db ...] [--out dashboard/index.html] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import html
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def esc(v: object) -> str:
    return html.escape("" if v is None else str(v))


def won(v: object) -> str:
    return f"{int(v):,}원" if v not in (None, "") else "-"


def num(v: object) -> str:
    return f"{int(v):,}" if v not in (None, "") else "-"


def latest_date(conn: sqlite3.Connection, override: str | None) -> str | None:
    if override:
        return override
    row = conn.execute("SELECT MAX(run_date) d FROM crawl_runs").fetchone()
    return row["d"] if row else None


def latest_runs(conn: sqlite3.Connection, run_date: str) -> list[sqlite3.Row]:
    # 타겟별 그 날짜의 가장 최근 run
    return conn.execute(
        """
        SELECT r.* FROM crawl_runs r
        JOIN (SELECT target_key, MAX(run_at) m FROM crawl_runs
              WHERE run_date=? GROUP BY target_key) x
          ON r.target_key=x.target_key AND r.run_at=x.m
        WHERE r.run_date=?
        ORDER BY r.run_at, r.target_key
        """,
        (run_date, run_date),
    ).fetchall()


def ranks_for(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM product_ranks WHERE run_id=? ORDER BY rank", (run_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# HTML 조각
# ---------------------------------------------------------------------------
def kpi_card(label: str, value: str, sub: str = "") -> str:
    sub_h = f'<div class="kpi-sub">{esc(sub)}</div>' if sub else ""
    return f'<div class="kpi"><div class="kpi-val">{esc(value)}</div><div class="kpi-label">{esc(label)}</div>{sub_h}</div>'


def bar(value: float, vmax: float, color: str) -> str:
    pct = 0 if vmax <= 0 else max(2, round(value / vmax * 100))
    return f'<div class="bar"><span style="width:{pct}%;background:{color}"></span></div>'


def badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{esc(text)}</span>'


def status_badge(status: str) -> str:
    m = {"success": ("성공", "ok"), "partial": ("부분", "warn"), "error": ("실패", "err"),
         "running": ("진행", "warn")}
    txt, cls = m.get(status, (status, "warn"))
    return badge(txt, cls)


def target_section(run: sqlite3.Row, rows: list[sqlite3.Row], has_qty: bool) -> str:
    head = (
        f'<div class="t-head">'
        f'<div><span class="t-title">{esc(run["label"] or run["target_key"])}</span>'
        f'<span class="t-key">{esc(run["target_key"])}</span></div>'
        f'<div class="t-meta">{status_badge(run["status"])}'
        f'<span class="chip">⏰ {esc(run["schedule"])}</span>'
        f'<span class="chip">TOP {esc(run["top_n"])}</span>'
        f'<span class="chip">{esc(run["item_count"])}건</span></div>'
        f'</div>'
    )

    # 막대 기준값
    qty_max = max((r["sales_qty"] or 0) for r in rows) if rows else 0
    dc_max = max((r["discount_rate"] or 0) for r in rows) if rows else 0

    body = ['<table class="t-table"><thead><tr>'
            '<th>#</th><th>상품명</th><th>판매가</th><th>할인</th>']
    body.append('<th>판매량</th>' if has_qty else '<th>리뷰</th>')
    body.append('<th>평점</th><th></th></tr></thead><tbody>')

    for r in rows[:10]:
        flags = ""
        if r["is_ad"]:
            flags += badge("AD", "ad")
        if r["is_sold_out"]:
            flags += badge("품절", "soldout")

        price_cell = won(r["sale_price"])
        if r["list_price"] and r["sale_price"] and r["list_price"] != r["sale_price"]:
            price_cell = f'<span class="strike">{won(r["list_price"])}</span> {won(r["sale_price"])}'

        if r["discount_rate"]:
            dc_cell = f'<span class="dc">{esc(r["discount_rate"])}%</span>{bar(r["discount_rate"], dc_max, "#f4733b")}'
        else:
            dc_cell = "-"

        if has_qty:
            q = r["sales_qty"]
            metric = f'{num(q)}{bar(q or 0, qty_max, "#3b82f6")}' if q is not None else "-"
        else:
            metric = num(r["review_count"])

        body.append(
            f'<tr><td class="rank">{esc(r["rank"])}</td>'
            f'<td class="name">{esc(r["product_name"])}</td>'
            f'<td>{price_cell}</td><td>{dc_cell}</td>'
            f'<td>{metric}</td>'
            f'<td>{("★ " + esc(r["rating"])) if r["rating"] else "-"}</td>'
            f'<td class="flags">{flags}</td></tr>'
        )
    body.append("</tbody></table>")
    return f'<section class="t-card">{head}{"".join(body)}</section>'


def build(db_path: Path, out_path: Path, date_override: str | None) -> Path:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    run_date = latest_date(conn, date_override)
    runs = latest_runs(conn, run_date) if run_date else []

    # KPI 집계
    total_items = 0
    discounts: list[int] = []
    ratings: list[float] = []
    sold_out = 0
    ok = 0
    sections: list[str] = []
    chart_rows: list[tuple[str, float, int]] = []  # (label, avg_dc, total_qty)

    for run in runs:
        rows = ranks_for(conn, run["id"])
        total_items += len(rows)
        if run["status"] == "success":
            ok += 1
        has_qty = any(r["sales_qty"] is not None for r in rows)
        d = [r["discount_rate"] for r in rows if r["discount_rate"]]
        discounts += d
        ratings += [r["rating"] for r in rows if r["rating"]]
        sold_out += sum(1 for r in rows if r["is_sold_out"])
        avg_dc = round(sum(d) / len(d), 1) if d else 0
        total_qty = sum((r["sales_qty"] or 0) for r in rows)
        chart_rows.append((run["label"] or run["target_key"], avg_dc, total_qty))
        sections.append(target_section(run, rows, has_qty))

    conn.close()

    avg_dc_all = round(sum(discounts) / len(discounts), 1) if discounts else 0
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0
    so_rate = round(sold_out / total_items * 100, 1) if total_items else 0

    kpis = "".join([
        kpi_card("수집 타겟", f"{len(runs)}", f"성공 {ok}/{len(runs)}"),
        kpi_card("수집 상품", f"{total_items:,}", "전체 순위 행"),
        kpi_card("평균 할인율", f"{avg_dc_all}%", f"{len(discounts)}개 상품"),
        kpi_card("평균 평점", f"★ {avg_rating}", f"{len(ratings)}개 상품"),
        kpi_card("품절 상품", f"{sold_out}", f"{so_rate}%"),
    ])

    # 차트: 타겟별 평균 할인율 + 판매량 합계
    dc_vmax = max((c[1] for c in chart_rows), default=0)
    qty_vmax = max((c[2] for c in chart_rows), default=0)
    chart_dc = "".join(
        f'<div class="crow"><div class="clabel">{esc(l)}</div>{bar(dc, dc_vmax, "#f4733b")}<div class="cval">{dc}%</div></div>'
        for l, dc, _ in chart_rows
    )
    chart_qty = "".join(
        f'<div class="crow"><div class="clabel">{esc(l)}</div>{bar(q, qty_vmax, "#3b82f6")}<div class="cval">{num(q)}</div></div>'
        for l, _, q in chart_rows if q
    ) or '<div class="empty">판매량 수집 타겟 없음 (톡딜·NS만 수집)</div>'

    title_date = run_date or "데이터 없음"
    body_html = "".join(sections) or '<div class="empty">표시할 데이터가 없습니다. scripts/seed_sample.py 또는 크롤러를 먼저 실행하세요.</div>'

    doc = HTML_TEMPLATE.format(
        date=esc(title_date), kpis=kpis,
        chart_dc=chart_dc, chart_qty=chart_qty, sections=body_html,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


HTML_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>쇼핑몰 랭킹 대시보드</title>
<style>
:root{{--bg:#0f1117;--card:#181b24;--card2:#1f2330;--line:#2a2f3d;--text:#e6e8ee;--muted:#9aa3b2;--accent:#6ee7b7}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}}
.wrap{{max-width:1280px;margin:0 auto;padding:28px 24px 60px}}
header.top{{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:22px;flex-wrap:wrap}}
h1{{font-size:24px;margin:0;letter-spacing:-.3px}}
h1 .dot{{color:var(--accent)}}
.sub{{color:var(--muted);font-size:14px}}
.kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px}}
.kpi{{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:14px;padding:16px 18px}}
.kpi-val{{font-size:26px;font-weight:700;letter-spacing:-.5px}}
.kpi-label{{color:var(--muted);font-size:13px;margin-top:4px}}
.kpi-sub{{color:#6b7280;font-size:12px;margin-top:2px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:26px}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}}
.panel h3{{margin:0 0 12px;font-size:14px;color:var(--muted);font-weight:600}}
.crow{{display:grid;grid-template-columns:120px 1fr 64px;align-items:center;gap:10px;margin:7px 0;font-size:13px}}
.clabel{{color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.cval{{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}}
.bar{{background:#10131b;border-radius:6px;height:10px;overflow:hidden}}
.bar span{{display:block;height:100%;border-radius:6px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.t-card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;overflow:hidden}}
.t-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:10px;flex-wrap:wrap}}
.t-title{{font-size:15px;font-weight:700}}
.t-key{{color:var(--muted);font-size:12px;margin-left:8px}}
.t-meta{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.chip{{background:#10131b;border:1px solid var(--line);color:var(--muted);font-size:11px;padding:2px 8px;border-radius:20px}}
.badge{{font-size:11px;padding:2px 7px;border-radius:6px;font-weight:600}}
.badge.ok{{background:#10331f;color:#6ee7b7}}
.badge.warn{{background:#3a2f10;color:#f4c430}}
.badge.err{{background:#3a1414;color:#f87171}}
.badge.ad{{background:#1e293b;color:#93c5fd;margin-left:3px}}
.badge.soldout{{background:#2a2a2a;color:#9aa3b2;margin-left:3px}}
table.t-table{{width:100%;border-collapse:collapse;font-size:12.5px}}
.t-table th{{text-align:left;color:var(--muted);font-weight:600;font-size:11px;padding:6px 6px;border-bottom:1px solid var(--line)}}
.t-table td{{padding:6px 6px;border-bottom:1px solid #20242f;vertical-align:middle}}
.t-table tr:last-child td{{border-bottom:none}}
td.rank{{color:var(--accent);font-weight:700;width:22px}}
td.name{{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.strike{{color:#6b7280;text-decoration:line-through;font-size:11px;margin-right:3px}}
.dc{{color:#f4733b;font-weight:700;margin-right:6px}}
.t-table .bar{{display:inline-block;width:54px;vertical-align:middle;margin-left:6px}}
td.flags{{text-align:right;white-space:nowrap}}
.empty{{color:var(--muted);padding:40px;text-align:center;border:1px dashed var(--line);border-radius:14px}}
.foot{{color:#5b6473;font-size:12px;margin-top:26px;text-align:center}}
</style></head>
<body><div class="wrap">
<header class="top">
  <div><h1>🛒 쇼핑몰 랭킹 대시보드<span class="dot">.</span></h1>
       <div class="sub">수집일자 <b>{date}</b> · 타겟별 최신 수집 결과</div></div>
</header>
<div class="kpis">{kpis}</div>
<div class="charts">
  <div class="panel"><h3>타겟별 평균 할인율</h3>{chart_dc}</div>
  <div class="panel"><h3>타겟별 판매량 합계 (톡딜 주문수 · NS 구매수)</h3>{chart_qty}</div>
</div>
<div class="grid">{sections}</div>
<div class="foot">shop-crawler · crawl_runs / product_ranks 기반 · 정적 생성 대시보드</div>
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
