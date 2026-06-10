#!/usr/bin/env python3
"""data/shop.db 의 수집 결과로 쇼핑몰 스타일 대시보드(HTML)를 생성한다.

- 플랫폼 채널 탭(G마켓 신선/가공, GS샵, 카카오 톡딜, NS몰=농산→수산→축산 통합)
- 상품 카드 그리드(썸네일·정가 취소선·할인율%·판매가), 5열×6줄, 모바일 반응형
- 수집일자 캘린더 모달: 데이터가 있는 날짜를 달력에서 골라 과거 데이터 조회
- 모든 날짜 데이터를 JSON 으로 한 파일에 임베드 → 외부 요청 없이 클라이언트에서
  렌더(완전 자급자족 HTML). 셀렉터/네트워크 무관하게 오프라인에서도 열린다.
- 각 채널의 전체 스크린샷(저장본) 링크 제공.

사용: python dashboard/build_dashboard.py [--db ...] [--out ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "wltjq1324-cloud/shop-crawler")

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


def all_dates(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT run_date FROM crawl_runs ORDER BY run_date DESC"
    ).fetchall()
    return [r[0] for r in rows]


def run_for(conn: sqlite3.Connection, target_key: str, run_date: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM crawl_runs
        WHERE target_key=? AND run_date=? AND item_count>0
        ORDER BY run_at DESC LIMIT 1
        """,
        (target_key, run_date),
    ).fetchone()


def ranks_for(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM product_ranks WHERE run_id=? ORDER BY rank", (run_id,)
    ).fetchall()


def card_dict(r: sqlite3.Row, qty_label: str, cat: str | None) -> dict:
    return {
        "rank": r["rank"],
        "name": r["product_name"] or "(이름 없음)",
        "img": r["image_url"] or "",
        "cat": cat,
        "listPrice": r["list_price"],
        "salePrice": r["sale_price"],
        "discountRate": r["discount_rate"],
        "soldOut": bool(r["is_sold_out"]),
        "ad": bool(r["is_ad"]),
        "rating": r["rating"],
        "review": r["review_count"],
        "qty": r["sales_qty"],
        "qtyLabel": qty_label,
        "url": r["product_url"] or "#",
    }


def build(db_path: Path, out_path: Path) -> Path:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    data: dict[str, dict] = {}
    for d in all_dates(conn):
        date_blob: dict[str, dict] = {}
        for tab in TABS:
            cards, shots, schedule, total = [], [], None, 0
            for tk in tab["targets"]:
                run = run_for(conn, tk, d)
                if not run:
                    continue
                schedule = schedule or run["schedule"]
                cat = (tab.get("cats") or {}).get(tk)
                qty_label = QTY_LABEL.get(tk, "구매")
                rows = ranks_for(conn, run["id"])
                total += len(rows)
                if run["screenshot_path"]:
                    shots.append({
                        "label": (tab.get("cats") or {}).get(tk, tab["label"]),
                        "url": f"https://github.com/{REPO_SLUG}/blob/main/{run['screenshot_path']}",
                    })
                for r in rows:
                    cards.append(card_dict(r, qty_label, cat))
            if cards:
                date_blob[tab["id"]] = {
                    "schedule": schedule, "items": total, "cards": cards, "shots": shots,
                }
        if date_blob:
            data[d] = date_blob

    conn.close()

    dates = sorted(data.keys(), reverse=True)
    payload = {
        "tabs": [{"id": t["id"], "label": t["label"]} for t in TABS],
        "dates": dates,
        "data": data,
    }
    doc = HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>쇼핑몰 베스트 랭킹</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#fff;color:#111;
  font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:20px 16px 60px}
header h1{font-size:22px;margin:0 0 2px;letter-spacing:-.3px}
.subrow{display:flex;align-items:center;gap:10px;color:#888;font-size:13px;margin-bottom:14px;flex-wrap:wrap}
.datebtn{display:inline-flex;align-items:center;gap:6px;border:1px solid #ddd;background:#fff;
  border-radius:20px;padding:6px 14px;font-size:14px;font-weight:700;color:#111;cursor:pointer}
.datebtn:active{background:#f5f5f5}
.tabbar{display:flex;gap:8px;overflow-x:auto;padding:4px 0 14px;position:sticky;top:0;
  background:#fff;z-index:10;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.tabbar::-webkit-scrollbar{display:none}
.tabbar button{flex:0 0 auto;padding:8px 16px;border:1px solid #ddd;border-radius:22px;
  font-size:14px;font-weight:600;color:#333;cursor:pointer;white-space:nowrap;background:#fff}
.tabbar button.on{background:#111;color:#fff;border-color:#111}
.phead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:6px 0 14px;flex-wrap:wrap}
.phead h2{font-size:17px;margin:0}
.phead em{font-style:normal;color:#e8453c;font-size:14px}
.phead .right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{font-size:12px;color:#777;background:#f5f5f5;border-radius:14px;padding:4px 10px}
.chip a{color:#3a7afe;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:22px 14px}
@media(max-width:1024px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:820px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:560px){.grid{grid-template-columns:repeat(2,1fr);gap:18px 10px}}
.card{display:block;text-decoration:none;color:inherit}
.thumb{position:relative;aspect-ratio:1/1;border-radius:10px;overflow:hidden;background:#f6f6f6;border:1px solid #eee}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.noimg{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:44px}
.rk{position:absolute;top:0;left:0;background:rgba(17,17,17,.85);color:#fff;font-size:12px;font-weight:700;
  min-width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:0 0 8px 0;z-index:2;padding:0 6px}
.bdg-ad{position:absolute;bottom:6px;left:6px;background:rgba(255,255,255,.92);border:1px solid #ccc;
  color:#666;font-size:10px;font-weight:700;padding:1px 5px;border-radius:4px;z-index:2}
.so{position:absolute;inset:0;background:rgba(255,255,255,.65);display:flex;align-items:center;justify-content:center;z-index:3}
.so span{background:rgba(17,17,17,.8);color:#fff;font-size:13px;font-weight:700;padding:6px 14px;border-radius:18px}
.info{padding:8px 2px 0}
.cat{display:inline-block;font-size:11px;font-weight:700;color:#0a7;background:#e9faf3;border-radius:4px;padding:1px 6px;margin-bottom:3px}
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
/* 캘린더 모달 */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.4);display:none;align-items:center;justify-content:center;z-index:100;padding:16px}
.modal.show{display:flex}
.cal{background:#fff;border-radius:16px;width:340px;max-width:100%;padding:18px;box-shadow:0 12px 40px rgba(0,0,0,.25)}
.cal-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.cal-head b{font-size:16px}
.cal-nav{border:none;background:#f3f3f3;width:34px;height:34px;border-radius:10px;font-size:16px;cursor:pointer}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center}
.cal-grid .dow{color:#aaa;font-size:11px;padding:4px 0}
.cal-cell{aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;font-size:13px;border-radius:9px;color:#ccc}
.cal-cell.has{color:#111;background:#eef3ff;font-weight:700;cursor:pointer}
.cal-cell.has:active{background:#dbe6ff}
.cal-cell.sel{background:#111;color:#fff}
.cal-foot{margin-top:12px;display:flex;justify-content:space-between;align-items:center}
.cal-foot button{border:none;background:#111;color:#fff;border-radius:10px;padding:8px 14px;font-size:13px;cursor:pointer}
.cal-foot .latest{background:#f3f3f3;color:#111}
.cal-note{color:#aaa;font-size:11px;margin-top:8px;text-align:center}
</style></head>
<body><div class="wrap">
<header><h1>🛒 쇼핑몰 베스트 랭킹</h1>
<div class="subrow">
  <button class="datebtn" id="dateBtn">📅 <span id="dateLabel">-</span> ▾</button>
  <span>채널 탭을 눌러 전환 · 날짜를 눌러 과거 데이터 조회</span>
</div></header>
<nav class="tabbar" id="tabbar"></nav>
<div id="panel"></div>
<footer>shop-crawler · crawl_runs / product_ranks 기반 정적 생성</footer>
</div>

<div class="modal" id="modal"><div class="cal">
  <div class="cal-head">
    <button class="cal-nav" id="prevM">‹</button>
    <b id="calTitle">2026.06</b>
    <button class="cal-nav" id="nextM">›</button>
  </div>
  <div class="cal-grid" id="calGrid"></div>
  <div class="cal-foot">
    <button class="latest" id="goLatest">최신으로</button>
    <button id="closeCal">닫기</button>
  </div>
  <div class="cal-note">파란 날짜 = 수집 데이터 있음</div>
</div></div>

<script>
const PAYLOAD = __PAYLOAD__;
const won = v => (v===null||v===undefined||v==="") ? "" : Number(v).toLocaleString("ko-KR")+"원";
const num = v => (v===null||v===undefined||v==="") ? "" : Number(v).toLocaleString("ko-KR");
const esc = s => String(s==null?"":s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const state = { date: PAYLOAD.dates[0] || null, tab: PAYLOAD.tabs[0].id, calMonth: null };
const dateSet = new Set(PAYLOAD.dates);

function cardHTML(c){
  const img = c.img ? `<img src="${esc(c.img)}" alt="${esc(c.name)}" loading="lazy" referrerpolicy="no-referrer">`
                    : `<div class="noimg">🛒</div>`;
  const ad = c.ad ? `<span class="bdg-ad">AD</span>` : "";
  const so = c.soldOut ? `<div class="so"><span>품절</span></div>` : "";
  const cat = c.cat ? `<span class="cat">${esc(c.cat)}</span>` : "";
  const hasDc = c.listPrice && c.salePrice && c.listPrice > c.salePrice;
  const orig = hasDc ? `<p class="orig"><s>나의 할인가 ${won(c.listPrice)}</s></p>` : `<p class="orig">&nbsp;</p>`;
  const dc = (hasDc && c.discountRate) ? `<b class="dc">${c.discountRate}%</b>` : "";
  const price = `<p class="prc">${dc}<b class="val">${won(c.salePrice)||"-"}</b></p>`;
  const bits=[];
  if(c.rating) bits.push("★ "+c.rating);
  if(c.review) bits.push("리뷰 "+num(c.review));
  if(c.qty) bits.push((c.qtyLabel||"구매")+" "+num(c.qty));
  const meta = bits.length ? `<p class="meta">${bits.join(" · ")}</p>` : `<p class="meta">&nbsp;</p>`;
  return `<a class="card" href="${esc(c.url)}" target="_blank" rel="noopener">
    <div class="thumb"><span class="rk">${c.rank}</span>${img}${ad}${so}</div>
    <div class="info">${cat}<p class="nm">${esc(c.name)}</p>${orig}${price}${meta}</div></a>`;
}

function renderTabs(){
  const bar = document.getElementById("tabbar");
  bar.innerHTML = PAYLOAD.tabs.map(t =>
    `<button data-id="${t.id}" class="${t.id===state.tab?'on':''}">${esc(t.label)}</button>`).join("");
  bar.querySelectorAll("button").forEach(b=>b.onclick=()=>{state.tab=b.dataset.id;render();});
}

function render(){
  document.getElementById("dateLabel").textContent = state.date || "데이터 없음";
  renderTabs();
  const panel = document.getElementById("panel");
  const tab = PAYLOAD.tabs.find(t=>t.id===state.tab);
  const blob = (PAYLOAD.data[state.date]||{})[state.tab];
  if(!blob){
    panel.innerHTML = `<div class="phead"><h2>${esc(tab.label)}</h2></div>
      <div class="empty">${esc(state.date||'')} 이 채널의 수집 데이터가 없습니다.</div>`;
    return;
  }
  const shots = (blob.shots||[]).map(s=>`<span class="chip"><a href="${esc(s.url)}" target="_blank" rel="noopener">📷 ${esc(s.label)} 스크린샷</a></span>`).join("");
  const sched = blob.schedule ? `<span class="chip">⏰ ${esc(blob.schedule)} 수집</span>` : "";
  panel.innerHTML = `<div class="phead"><h2>${esc(tab.label)} <em>TOP ${blob.items}</em></h2>
      <div class="right">${sched}${shots}</div></div>
      <div class="grid">${blob.cards.map(cardHTML).join("")}</div>`;
}

/* ---- 캘린더 모달 ---- */
const modal = document.getElementById("modal");
function openCal(){
  state.calMonth = (state.date||PAYLOAD.dates[0]||"2026-06-01").slice(0,7);
  drawCal(); modal.classList.add("show");
}
function closeCal(){ modal.classList.remove("show"); }
function shiftMonth(delta){
  let [y,m] = state.calMonth.split("-").map(Number);
  m += delta; if(m<1){m=12;y--;} if(m>12){m=1;y++;}
  state.calMonth = `${y}-${String(m).padStart(2,"0")}`; drawCal();
}
function drawCal(){
  const [y,m] = state.calMonth.split("-").map(Number);
  document.getElementById("calTitle").textContent = `${y}.${String(m).padStart(2,"0")}`;
  const first = new Date(y, m-1, 1).getDay();
  const days = new Date(y, m, 0).getDate();
  const dows = ["일","월","화","수","목","금","토"];
  let html = dows.map(d=>`<div class="dow">${d}</div>`).join("");
  for(let i=0;i<first;i++) html += `<div class="cal-cell"></div>`;
  for(let d=1; d<=days; d++){
    const iso = `${y}-${String(m).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const has = dateSet.has(iso);
    const sel = iso===state.date;
    html += `<div class="cal-cell ${has?'has':''} ${sel?'sel':''}" data-iso="${iso}">${d}</div>`;
  }
  const grid = document.getElementById("calGrid");
  grid.innerHTML = html;
  grid.querySelectorAll(".cal-cell.has").forEach(c=>c.onclick=()=>{
    state.date=c.dataset.iso; closeCal(); render();
  });
}
document.getElementById("dateBtn").onclick = openCal;
document.getElementById("prevM").onclick = ()=>shiftMonth(-1);
document.getElementById("nextM").onclick = ()=>shiftMonth(1);
document.getElementById("closeCal").onclick = closeCal;
document.getElementById("goLatest").onclick = ()=>{ state.date=PAYLOAD.dates[0]; closeCal(); render(); };
modal.onclick = e=>{ if(e.target===modal) closeCal(); };

if(!state.date){
  document.getElementById("panel").innerHTML = `<div class="empty">아직 수집된 데이터가 없습니다.</div>`;
  document.getElementById("dateLabel").textContent = "데이터 없음";
} else { render(); }
</script>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "shop.db"))
    ap.add_argument("--out", default=str(ROOT / "dashboard" / "index.html"))
    args = ap.parse_args(argv)
    out = build(Path(args.db), Path(args.out))
    print(f"대시보드 생성: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
