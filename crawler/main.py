"""크롤러 엔트리포인트.

기본 동작: targets.yaml 을 읽어 "지금 수집해야 하는(due)" 타겟만 크롤링한다.
GitHub Actions 워크플로가 각 distinct schedule 시각마다 기동되므로, 매 기동에서
해당 시각에 예정된 타겟만 실행되는 구조다.

옵션:
  --all            schedule 무시하고 모든 타겟 실행
  --keys k1,k2     특정 타겟만 실행(schedule 무시)
  --list           실행하지 않고 due 판정 결과만 출력
  --headed         브라우저 헤드풀(디버깅)
  --db / --targets / --exports / --screenshots  경로 지정
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

from . import db as dbmod
from .config import ROOT, Target, load_targets
from .exporter import export_csv


def select_targets(targets: list[Target], args, now: dt.datetime) -> list[Target]:
    if args.keys:
        wanted = {k.strip() for k in args.keys.split(",") if k.strip()}
        return [t for t in targets if t.key in wanted]
    if args.all:
        return list(targets)
    # 기본: due 판정
    return [t for t in targets if t.is_due(now.astimezone(t.tz))]


def run_target(page, conn, target: Target, now_kst: dt.datetime, paths: dict) -> dict:
    run_date = now_kst.strftime("%Y-%m-%d")
    screenshot_path = Path(paths["screenshots"]) / run_date / f"{target.key}.png"
    csv_path = Path(paths["exports"]) / f"{run_date}_{target.key}.csv"

    run_id = dbmod.start_run(
        conn,
        target_key=target.key,
        label=target.label,
        url=target.url,
        run_date=run_date,
        run_at=now_kst,
        schedule=target.schedule,
        top_n=target.top_n,
    )

    # Playwright 의존 파서는 실제 크롤링 시점에만 import.
    from .parsers import get_parser

    status = "success"
    error = None
    rows = []
    try:
        parser = get_parser(target.parser)
        rows = parser.crawl(page, target.url, target.top_n, screenshot_path)
        if not rows:
            status = "partial"
            # 0건이면 셀렉터 보정용으로 실제 렌더된 HTML 을 덤프(DEBUG_HTML=1 일 때)
            if os.environ.get("DEBUG_HTML") == "1":
                try:
                    dbg = Path(paths.get("debug", "debug")) / run_date / f"{target.key}.html"
                    dbg.parent.mkdir(parents=True, exist_ok=True)
                    dbg.write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
    except Exception as e:  # noqa: BLE001
        status = "error"
        error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    if rows:
        dbmod.insert_ranks(conn, run_id, target.key, run_date, rows)
        export_csv(rows, csv_path)

    dbmod.finish_run(
        conn,
        run_id,
        status=status,
        item_count=len(rows),
        screenshot_path=str(screenshot_path) if screenshot_path.exists() else None,
        csv_path=str(csv_path) if csv_path.exists() else None,
        error=error,
    )
    return {"key": target.key, "status": status, "count": len(rows), "error": error}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="일일 쇼핑몰 랭킹 크롤러")
    parser.add_argument("--targets", default=str(ROOT / "targets.yaml"))
    parser.add_argument("--db", default=str(ROOT / "data" / "shop.db"))
    parser.add_argument("--exports", default=str(ROOT / "exports"))
    parser.add_argument("--screenshots", default=str(ROOT / "screenshots"))
    parser.add_argument("--keys", default="", help="콤마구분 타겟 key (schedule 무시)")
    parser.add_argument("--all", action="store_true", help="schedule 무시하고 전체 실행")
    parser.add_argument("--list", action="store_true", help="due 판정만 출력")
    parser.add_argument("--headed", action="store_true", help="브라우저 헤드풀")
    parser.add_argument("--now", default="", help="기준 시각 ISO(테스트용, KST)")
    args = parser.parse_args(argv)

    targets = load_targets(args.targets)
    kst = ZoneInfo("Asia/Seoul")
    now_kst = dt.datetime.fromisoformat(args.now).replace(tzinfo=kst) if args.now else dt.datetime.now(kst)

    selected = select_targets(targets, args, now_kst)

    if args.list:
        print(f"[기준 시각 KST] {now_kst.isoformat()}")
        for t in targets:
            due = t.is_due(now_kst.astimezone(t.tz))
            mark = "DUE " if t in selected else ("due " if due else "    ")
            print(f"  {mark} {t.key:22s} schedule={t.schedule}  parser={t.parser}  top_n={t.top_n}")
        print(f"\n선택된 타겟 {len(selected)}개: {[t.key for t in selected]}")
        return 0

    if not selected:
        print(f"[{now_kst.isoformat()}] 지금 수집할 타겟이 없습니다(due 없음). --all 로 강제 실행 가능.")
        return 0

    paths = {"exports": args.exports, "screenshots": args.screenshots}
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn)

    # Playwright 는 실제 크롤링 시점에만 import (—list 등에서는 불필요)
    from playwright.sync_api import sync_playwright

    results = []
    print(f"[{now_kst.isoformat()}] 크롤링 시작: {[t.key for t in selected]}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            viewport={"width": 1366, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        for t in selected:
            page = context.new_page()
            try:
                res = run_target(page, conn, t, now_kst, paths)
            finally:
                page.close()
            results.append(res)
            tag = {"success": "OK", "partial": "부분", "error": "실패"}.get(res["status"], res["status"])
            print(f"  - {t.key:22s} [{tag}] {res['count']}건")
            if res["error"]:
                print(f"      └ {res['error'].splitlines()[0]}")
        browser.close()

    conn.close()
    n_err = sum(1 for r in results if r["status"] == "error")
    print(f"\n완료: 성공 {len(results) - n_err} / 실패 {n_err}")
    # 일부 실패해도 워크플로 자체는 실패시키지 않음(스크린샷/부분데이터 보존)
    return 0


if __name__ == "__main__":
    sys.exit(main())
