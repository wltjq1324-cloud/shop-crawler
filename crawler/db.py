"""SQLite 스키마 및 저장 로직 (crawl_runs + product_ranks)."""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .models import ProductRank

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_key      TEXT    NOT NULL,
    label           TEXT,
    url             TEXT    NOT NULL,
    run_date        TEXT    NOT NULL,   -- YYYY-MM-DD (KST)
    run_at          TEXT    NOT NULL,   -- ISO8601 timestamp (KST)
    schedule        TEXT,               -- 적용된 수집 시각 "HH:MM"
    top_n           INTEGER NOT NULL,
    status          TEXT    NOT NULL,   -- success | partial | error
    item_count      INTEGER NOT NULL DEFAULT 0,
    screenshot_path TEXT,
    csv_path        TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS product_ranks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    target_key    TEXT    NOT NULL,
    run_date      TEXT    NOT NULL,
    rank          INTEGER NOT NULL,
    product_name  TEXT,
    product_id    TEXT,
    list_price    INTEGER,             -- 정가
    sale_price    INTEGER,             -- 판매가
    discount_rate INTEGER,             -- 할인율(%)
    sales_qty     INTEGER,             -- 톡딜 주문수 / NS 구매수 (지마켓·GS샵 NULL)
    order_count   INTEGER,             -- 주문수
    review_count  INTEGER,             -- 리뷰수
    rating        REAL,                -- 평점
    is_sold_out   INTEGER,             -- 품절 여부 (0/1)
    is_ad         INTEGER,             -- 광고 여부 (0/1)
    product_url   TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_key_date  ON crawl_runs(target_key, run_date);
CREATE INDEX IF NOT EXISTS idx_ranks_run      ON product_ranks(run_id);
CREATE INDEX IF NOT EXISTS idx_ranks_key_date ON product_ranks(target_key, run_date);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def start_run(
    conn: sqlite3.Connection,
    *,
    target_key: str,
    label: str,
    url: str,
    run_date: str,
    run_at: dt.datetime,
    schedule: str,
    top_n: int,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO crawl_runs
            (target_key, label, url, run_date, run_at, schedule, top_n, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'running')
        """,
        (target_key, label, url, run_date, run_at.isoformat(), schedule, top_n),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    item_count: int,
    screenshot_path: str | None,
    csv_path: str | None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE crawl_runs
           SET status = ?, item_count = ?, screenshot_path = ?, csv_path = ?, error = ?
         WHERE id = ?
        """,
        (status, item_count, screenshot_path, csv_path, error, run_id),
    )
    conn.commit()


def insert_ranks(
    conn: sqlite3.Connection,
    run_id: int,
    target_key: str,
    run_date: str,
    rows: list[ProductRank],
) -> None:
    payload = []
    for r in rows:
        d = asdict(r)
        payload.append(
            (
                run_id,
                target_key,
                run_date,
                d["rank"],
                d["product_name"],
                d["product_id"],
                d["list_price"],
                d["sale_price"],
                d["discount_rate"],
                d["sales_qty"],
                d["order_count"],
                d["review_count"],
                d["rating"],
                _bool(d["is_sold_out"]),
                _bool(d["is_ad"]),
                d["product_url"],
            )
        )
    conn.executemany(
        """
        INSERT INTO product_ranks
            (run_id, target_key, run_date, rank, product_name, product_id,
             list_price, sale_price, discount_rate, sales_qty, order_count,
             review_count, rating, is_sold_out, is_ad, product_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    conn.commit()


def _bool(v: object) -> int | None:
    if v is None:
        return None
    return 1 if v else 0
