"""숫자/텍스트 파싱 헬퍼."""

from __future__ import annotations

import re

_NUM_RE = re.compile(r"-?\d[\d,]*")
_FLOAT_RE = re.compile(r"\d+(?:\.\d+)?")


def to_int(text: str | None) -> int | None:
    """문자열에서 첫 번째 정수를 추출. '12,900원' -> 12900."""
    if text is None:
        return None
    m = _NUM_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def to_count(text: str | None) -> int | None:
    """'주문 1.2만', '구매 3,456' 같은 카운트 표현을 정수로.

    한국식 만/천 단위 약어를 지원한다. '1.2만' -> 12000.
    """
    if text is None:
        return None
    t = text.replace(",", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*만", t)
    if m:
        return int(round(float(m.group(1)) * 10_000))
    m = re.search(r"(\d+(?:\.\d+)?)\s*천", t)
    if m:
        return int(round(float(m.group(1)) * 1_000))
    return to_int(t)


def to_percent(text: str | None) -> int | None:
    """'30%' -> 30."""
    if text is None:
        return None
    m = re.search(r"(\d+)\s*%", text)
    if m:
        return int(m.group(1))
    return to_int(text)


def to_float(text: str | None) -> float | None:
    """'4.8점' -> 4.8."""
    if text is None:
        return None
    m = _FLOAT_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    return t or None


def compute_discount(list_price: int | None, sale_price: int | None) -> int | None:
    """정가/판매가로 할인율(%) 역산 (할인율이 표기 안 된 경우 보조)."""
    if not list_price or not sale_price or list_price <= 0:
        return None
    if sale_price >= list_price:
        return 0
    return int(round((list_price - sale_price) / list_price * 100))
