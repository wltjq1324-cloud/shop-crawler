"""CSV 산출물 생성: exports/{date}_{key}.csv."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import ProductRank


def export_csv(rows: list[ProductRank], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(ProductRank.csv_header())
        for r in rows:
            writer.writerow(r.csv_row())
    return out_path
