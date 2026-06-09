#!/usr/bin/env python3
"""targets.yaml 의 distinct schedule(KST)을 GitHub Actions cron(UTC)으로 변환.

워크플로 cron 은 UTC 기준이므로 KST(UTC+9)에서 9시간을 빼서 출력한다.
출력 라인을 .github/workflows/crawl.yml 의 `schedule:` 블록에 붙여넣으면 된다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import distinct_schedules, load_targets  # noqa: E402


def kst_to_utc_cron(hhmm: str) -> str:
    hh, mm = (int(x) for x in hhmm.split(":"))
    utc_hh = (hh - 9) % 24
    # 분 단위 underflow 는 없음(시 단위만 빼므로). day 경계는 cron 에서 무시 가능.
    return f"{mm} {utc_hh} * * *"


def main() -> int:
    targets = load_targets()
    print("# targets.yaml 기준 자동 생성된 cron (UTC). crawl.yml 의 schedule 에 반영하세요.")
    for s in distinct_schedules(targets):
        cron = kst_to_utc_cron(s)
        keys = [t.key for t in targets if t.schedule == s]
        print(f"  - cron: '{cron}'   # {s} KST -> {', '.join(keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
