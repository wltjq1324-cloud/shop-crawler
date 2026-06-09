# shop-crawler

일일 쇼핑몰 랭킹 크롤러. **Python + Playwright + SQLite + CSV** 스택으로 매일
지정 시각(기본 09:00 KST)에 각 쇼핑몰 베스트/카테고리 랭킹을 수집한다.

## 수집 대상

| key | 플랫폼 | top_n | sales_qty | 수집 시각(KST) |
|---|---|---|---|---|
| `gmarket_fresh` | G마켓 신선식품 베스트 | 30 | — (NULL) | 09:00 |
| `gmarket_processed` | G마켓 가공식품 베스트 | 30 | — (NULL) | 09:00 |
| `gsshop_best` | GS샵 NOW 베스트 | 30 | — (NULL) | 09:00 |
| `kakao_talkdeal_food` | 카카오 톡딜 식품 | 30 | 주문수 | **10:00** |
| `nsmall_nongsan` | NS몰 농산 | 10 | 구매수 | 09:00 |
| `nsmall_susan` | NS몰 수산 | 10 | 구매수 | 09:00 |
| `nsmall_chuksan` | NS몰 축산 | 10 | 구매수 | 09:00 |

각 타겟마다 **(1) 전체 스크린샷 저장**, **(2) 순위 1~N 상품 파싱**을 수행한다.

### 수집 필드
`list_price`(정가), `sale_price`(판매가), `discount_rate`(할인율%),
`sales_qty`(톡딜 주문수 / NS 구매수, 지마켓·GS샵은 NULL), `order_count`(주문수),
`review_count`(리뷰수), `rating`(평점), `is_sold_out`(품절), `is_ad`(광고),
`product_url` — 그리고 `rank`, `product_name`.

## ★ 사이트별 수집 시각 (targets.yaml 로 덮어쓰기)

행사 오픈/마감 시각이 플랫폼마다 달라 **타겟별로 수집 시각을 개별 조정**할 수 있다.

```yaml
defaults:
  schedule: "09:00"        # 전역 기본 수집 시각(KST)
  due_window_minutes: 55   # cron 이 늦게 떠도 인정하는 윈도

targets:
  - key: kakao_talkdeal_food
    schedule: "10:00"      # ← 이 타겟만 10시로 덮어쓰기 (톡딜 오픈 시각)
```

### 동작 원리
GitHub Actions cron 은 워크플로 단위(전역)라 사이트별 시각을 직접 줄 수 없다.
그래서:

1. 워크플로는 `targets.yaml` 의 **distinct schedule 시각마다 cron 으로 기동**한다
   (09:00·10:00 KST → 00:00·01:00 UTC).
2. 매 기동에서 크롤러가 **"지금 due 인 타겟"만 골라 실행**한다.
   `0 ≤ (현재 − 예정시각) < due_window_minutes` 이면 due.

schedule 을 추가/변경하면 cron 도 갱신해야 한다:

```bash
python scripts/gen_cron.py     # KST schedule → UTC cron 출력
# 출력 라인을 .github/workflows/crawl.yml 의 schedule: 블록에 반영
```

## 산출물

- `data/shop.db` — SQLite (`crawl_runs` + `product_ranks` 두 테이블)
- `exports/{date}_{key}.csv` — 타겟별 일자 CSV (UTF-8 BOM, 엑셀 호환)
- `screenshots/{date}/{key}.png` — 타겟별 전체 페이지 스크린샷

CI 는 매 실행 결과를 워크플로 아티팩트로 업로드하고, 레포에도 커밋해 히스토리를 누적한다.

### 스키마 요약
- **crawl_runs**: 실행 메타 (target_key, run_date, run_at, schedule, top_n, status,
  item_count, screenshot_path, csv_path, error)
- **product_ranks**: 상품 순위 행 (run_id FK, rank, 위 수집 필드 전체)

## 로컬 실행

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium

python -m crawler.main --list                 # due 판정만 확인(크롤링 X)
python -m crawler.main                         # 지금 due 인 타겟 크롤링
python -m crawler.main --all                   # schedule 무시, 전체 실행
python -m crawler.main --keys gmarket_fresh    # 특정 타겟만
python -m crawler.main --all --now "2026-06-09T10:30:00"  # 기준시각 지정(테스트)
```

## 스케줄 (GitHub Actions)

`.github/workflows/crawl.yml` 의 cron 으로 매일 자동 실행되며, `workflow_dispatch`
로 수동 실행(특정 key / 전체)도 가능하다.

## 구조

```
crawler/
  config.py          # targets.yaml 로드 + due(★ 시각) 판정
  db.py              # SQLite 스키마/저장
  models.py          # ProductRank 데이터 모델
  exporter.py        # CSV 출력
  utils.py           # 숫자/텍스트 파싱 헬퍼
  main.py            # 엔트리포인트(타겟 선택 → 크롤 → 저장)
  parsers/
    base.py          # navigate→스크롤→전체 스크린샷→extract 공통 흐름
    extract_js.py    # 셀렉터 후보 기반 카드 추출 JS 러너
    gmarket.py gsshop.py kakao_talkdeal.py nsmall.py
scripts/gen_cron.py  # KST schedule → UTC cron 생성
targets.yaml         # 수집 대상/시각 설정
```

## 참고: 파서 견고성

각 사이트 파서는 **셀렉터 후보 목록**을 두고 첫 매칭을 사용한다. 사이트 마크업이
바뀌어 일부 필드를 못 찾아도 해당 필드는 `NULL` 로 남기고, **전체 스크린샷은
항상 저장**한다. 마크업이 크게 바뀌면 각 파서의 `CONFIG` 셀렉터 후보를 보강하면 된다.
(실제 운영 사이트는 안티봇/동적 로딩이 있어, 첫 도입 시 스크린샷으로 셀렉터를
한 번 점검하는 것을 권장한다.)
