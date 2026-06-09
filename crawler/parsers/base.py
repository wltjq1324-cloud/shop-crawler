"""파서 베이스: Playwright 페이지 생명주기 + 공통 헬퍼.

각 사이트 파서는 BaseParser 를 상속하고 `extract()` 만 구현한다.
공통 흐름(navigate -> lazy-load 스크롤 -> 전체 스크린샷 -> extract)은
`crawl()` 에서 처리한다. 셀렉터가 깨져 0건이 나와도 스크린샷은 항상 남긴다.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, TimeoutError as PWTimeout

from ..models import ProductRank


class BaseParser:
    name: str = "base"

    def __init__(self, base_url: str = ""):
        self.base_url = base_url

    # --- 하위 클래스가 구현 -------------------------------------------------
    def extract(self, page: Page, top_n: int) -> list[ProductRank]:
        raise NotImplementedError

    # --- 공통 흐름 ----------------------------------------------------------
    def crawl(self, page: Page, url: str, top_n: int, screenshot_path: Path) -> list[ProductRank]:
        self.base_url = url
        self.goto(page, url)
        self.auto_scroll(page)
        self.save_screenshot(page, screenshot_path)
        rows = self.extract(page, top_n)
        return rows[:top_n]

    def goto(self, page: Page, url: str) -> None:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except PWTimeout:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PWTimeout:
            pass

    def auto_scroll(self, page: Page, steps: int = 12, pause_ms: int = 400) -> None:
        """무한스크롤/지연로딩 콘텐츠를 트리거하기 위해 천천히 스크롤."""
        try:
            for _ in range(steps):
                page.mouse.wheel(0, 1600)
                page.wait_for_timeout(pause_ms)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
        except Exception:
            pass

    def save_screenshot(self, page: Page, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(path), full_page=True)
        except Exception:
            # full_page 실패 시 viewport 라도 저장
            try:
                page.screenshot(path=str(path))
            except Exception:
                pass

    def absolutize(self, href: str | None) -> str | None:
        if not href:
            return None
        if href.startswith("http"):
            return href
        return urljoin(self.base_url, href)
