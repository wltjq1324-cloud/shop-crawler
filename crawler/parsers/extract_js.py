"""DOM 에서 상품 카드를 추출하는 공용 JS 러너.

사이트별로 셀렉터 후보(config)만 다르게 주면 동일한 방식으로 카드 텍스트를
긁어온다. 실제 사이트 마크업이 바뀌어도 후보 셀렉터를 늘리면 대응 가능하고,
못 찾은 필드는 None 으로 남는다(스크린샷은 별도로 항상 저장).
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

# config 스키마:
# {
#   "cardSelectors": ["sel1", "sel2", ...],     # 첫 번째로 매칭되는 셀렉터 사용
#   "fields": {                                  # 각 필드: 카드 내부 후보 셀렉터 목록
#       "name": ["..."],
#       "listPrice": ["..."],
#       "salePrice": ["..."],
#       "discount": ["..."],
#       "salesQty": ["..."],
#       "reviewCount": ["..."],
#       "rating": ["..."],
#   },
#   "linkSelectors": ["a"],
#   "soldOut": {"selectors": [...], "keywords": ["품절", "SOLD OUT"]},
#   "ad": {"selectors": [...], "keywords": ["광고", "AD"]},
# }

_JS = r"""
(config) => {
  const pickNodes = (root, selectors) => {
    for (const sel of selectors) {
      const nodes = root.querySelectorAll(sel);
      if (nodes && nodes.length) return Array.from(nodes);
    }
    return [];
  };
  const textOf = (card, selectors) => {
    if (!selectors) return null;
    for (const sel of selectors) {
      const el = card.querySelector(sel);
      if (el) {
        const t = (el.textContent || "").trim();
        if (t) return t;
      }
    }
    return null;
  };
  const hasMatch = (card, spec) => {
    if (!spec) return null;
    const sels = spec.selectors || [];
    for (const sel of sels) {
      if (card.querySelector(sel)) return true;
    }
    const kws = spec.keywords || [];
    if (kws.length) {
      const txt = (card.textContent || "");
      for (const kw of kws) {
        if (txt.includes(kw)) return true;
      }
    }
    return false;
  };

  const cards = pickNodes(document, config.cardSelectors);
  const out = [];
  const limit = config.limit || cards.length;
  for (let i = 0; i < cards.length && out.length < limit; i++) {
    const card = cards[i];
    const f = config.fields || {};
    let href = null;
    const linkSels = config.linkSelectors || ["a"];
    for (const sel of linkSels) {
      const a = card.querySelector(sel);
      if (a && a.getAttribute("href")) { href = a.getAttribute("href"); break; }
    }
    out.push({
      name: textOf(card, f.name),
      listPrice: textOf(card, f.listPrice),
      salePrice: textOf(card, f.salePrice),
      discount: textOf(card, f.discount),
      salesQty: textOf(card, f.salesQty),
      orderCount: textOf(card, f.orderCount),
      reviewCount: textOf(card, f.reviewCount),
      rating: textOf(card, f.rating),
      href: href,
      isSoldOut: hasMatch(card, config.soldOut),
      isAd: hasMatch(card, config.ad),
    });
  }
  return out;
}
"""


def evaluate_cards(page: Page, config: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return page.evaluate(_JS, config) or []
    except Exception:
        return []
