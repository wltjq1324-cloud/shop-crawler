"""targets.yaml 로딩 및 스케줄(★ 사이트별 수집 시각) 처리."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGETS_FILE = ROOT / "targets.yaml"


@dataclass
class Target:
    """단일 수집 대상."""

    key: str
    url: str
    parser: str
    top_n: int
    schedule: str               # "HH:MM" (KST 등 timezone 기준)
    timezone: str
    due_window_minutes: int
    label: str = ""
    # sales_qty 를 어느 소스에서 채울지. None 이면 sales_qty 미수집(NULL).
    # 예) "order_count"(톡딜 주문수), "purchase_count"(NS 구매수)
    sales_qty_source: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def scheduled_dt(self, now: dt.datetime) -> dt.datetime:
        """now(타겟 timezone aware)와 같은 날짜의 예정 수집 시각."""
        hh, mm = (int(x) for x in self.schedule.split(":"))
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)

    def is_due(self, now: dt.datetime | None = None) -> bool:
        """현재 시각이 이 타겟의 수집 윈도 안에 있는지.

        0 <= (now - scheduled) < due_window_minutes 이면 수집 대상.
        Actions cron 이 몇 분 늦게 떠도 인정하기 위한 윈도를 둔다.
        """
        now = now or dt.datetime.now(self.tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=self.tz)
        scheduled = self.scheduled_dt(now)
        delta_min = (now - scheduled).total_seconds() / 60.0
        return 0 <= delta_min < self.due_window_minutes


def load_targets(path: str | Path = DEFAULT_TARGETS_FILE) -> list[Target]:
    """targets.yaml 을 읽어 Target 목록으로 변환(defaults 머지 포함)."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults: dict[str, Any] = data.get("defaults", {}) or {}
    targets: list[Target] = []

    for raw in data.get("targets", []) or []:
        merged = {**defaults, **raw}
        targets.append(
            Target(
                key=merged["key"],
                url=merged["url"],
                parser=merged["parser"],
                top_n=int(merged.get("top_n", 30)),
                schedule=str(merged.get("schedule", "09:00")),
                timezone=str(merged.get("timezone", "Asia/Seoul")),
                due_window_minutes=int(merged.get("due_window_minutes", 55)),
                label=str(merged.get("label", "")),
                sales_qty_source=merged.get("sales_qty_source"),
                raw=merged,
            )
        )
    return targets


def distinct_schedules(targets: list[Target]) -> list[str]:
    """워크플로 cron 생성을 위한 distinct 한 schedule 목록(정렬)."""
    return sorted({t.schedule for t in targets})
