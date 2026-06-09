"""사이트별 파서 레지스트리."""

from __future__ import annotations

from .base import BaseParser
from .gmarket import GmarketParser
from .gsshop import GsshopParser
from .kakao_talkdeal import KakaoTalkdealParser
from .nsmall import NsmallParser

_REGISTRY: dict[str, type[BaseParser]] = {
    GmarketParser.name: GmarketParser,
    GsshopParser.name: GsshopParser,
    KakaoTalkdealParser.name: KakaoTalkdealParser,
    NsmallParser.name: NsmallParser,
}


def get_parser(name: str) -> BaseParser:
    try:
        return _REGISTRY[name]()
    except KeyError as e:
        raise ValueError(f"알 수 없는 parser: {name!r}. 사용 가능: {sorted(_REGISTRY)}") from e
