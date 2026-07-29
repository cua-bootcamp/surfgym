# travelhub_ad_web 단독 커버리지 — OSWorld chrome 태스크 46개

## 목적

OSWorld 평가를 **베끼지 않고** 통과할 수 있는 학습 태스크를 만드는 것이 목표다.
따라서 판정 기준은 도메인 일치나 사이트 외형이 아니라 **핵심 action trajectory가 같은가**이다.
디테일(도시 이름, 필터 항목명, 상품 종류)은 달라도 되고, 오히려 다른 편이 암기·치팅 위험을 낮춘다.

이 문서는 `travelhub_ad_web` **한 개 앱만으로** OSWorld chrome 태스크 46개 중 어디까지
궤적을 재현할 수 있는지 판정한 결과다.

결론: **46개 중 웹사이트로 재현 가능한 것이 26개이고, 그중 20개를 travelhub 하나가 덮는다.**
나머지 6개는 장바구니(1)·가용성표(1)·날씨(1)·비교표(1)·계산기(1)·이름검색(1)이다.

## 원본 파일

이 디렉터리에는 판정 대상 22개(커버 20 + 조건부 2)의 **수정하지 않은 원본 사본**이 들어 있다.
빌드 파이프라인은 읽지 않는다 — `SeedReader`는 `seeds/*.json`만, `pack_tasks.py`는 `tasks/*.json`만 글롭한다.

| 디렉터리 | 레포 | 커밋 | 내용 |
|---|---|---|---|
| `xlang-ai_OSWorld/` | `xlang-ai/OSWorld` (OSWorld 1.0) | `b7db4d8` (2026-07-19) | 22개 전부 |
| `xlang-ai_OSWorld-V2/` | `xlang-ai/OSWorld-V2` (OSWorld 2.0, 2026-06-26 공개) | `c261cb5` (2026-06-30) | 1.0과 **내용이 다른** 16개만 |

두 레포는 별개다. 태스크 도메인 구성도 chrome 태스크 46개라는 개수도 같고, 같은 id의 태스크를
2.0에서 손본 관계다. 전 파일 `diff -q`로 원본과 바이트 동일함을 확인했다.

1.0과 2.0이 동일한 6개: `f79439ad` `0d8b7de3` `121ba48f` `82279c77` `a728a36e` `b4f95342`.

### 이식에 영향 있는 1.0 / 2.0 차이

- `1704f00f` — 2.0에서 채점기가 재구성됐다. 1.0은 `conj: "or"`로 두 분기를 두고 한쪽이
  "week after next Monday"라는 대체 날짜 해석을 허용한다(정답 날짜가 두 벌). 2.0은 OR을 없애고
  (위치·차종·정렬) / (픽업·반납 날짜) 두 검사로 분리했다. **2.0을 기준으로 삼는다.**
- `82bc8d6a` — 1.0은 도착지를 `["STO","ARN"]` 중 아무거나 + `expect_in_result: true`로 느슨하게
  본다. 2.0은 `"STO"` 단일값에 부분매칭을 껐다(더 엄격).
- `b7895e80` — 2.0에서 instruction이 축약됐고("Sort the search results by price and stay on the
  results page." 삭제) xpath가 `data-automation` 기반에서 `/html/body/div[1]/main/...` 절대경로로
  바뀌었다. 정렬 요구가 사라져 태스크가 약해졌으므로 **1.0을 기준으로 삼는다.**
- 나머지 차이는 대부분 `proxy` 플래그 토글이라 무시해도 된다.

`benchmark_releases/osworld-v2-2026.06.24.json`은 태스크 id 목록이 아니라 HuggingFace 데이터셋·
이미지 태그를 가리키는 포인터 매니페스트다. 따라서 이 22개가 2.0 공식 릴리스에 포함되는지는
그 파일로 판정할 수 없다 — **미확인**.

## travelhub_ad_web이 실제로 가진 능력 (소스 확인)

| 도메인 | URL에 실리는 검색 조건 | 결과 페이지 필터 | 정렬 |
|---|---|---|---|
| 항공 | `originCode` `destCode` `depart` `return` `tripType`(one-way/round-trip/multi-city) `adults` `children` `infants` `cabin`(economy/premium_economy/business/first) `direct` | 경유수(0/1/2+), 항공사, 가격대 | best / cheapest / fastest |
| 렌터카 | `pickup` `dropoff` `pickup_date` `pickup_time` `dropoff_date` `dropoff_time` `brand` `young_driver` | 차종(Small/Medium/**Large**/SUV/Luxury/People Carrier/Electric), 업체, 변속기, 연료(Petrol/Diesel/Hybrid/**Electric**), 가격대 | recommended / price-low / price-high / rating |
| 호텔 | `destination` `checkin` `checkout` `adults` `children` `rooms` `entire_home` `work` `flex_days` | 성급, 리뷰점수, 숙소유형, 가격대 | top-picks / **price-low** / star-price / top-reviewed |
| 어트랙션 | `sort_by` 등 | 하위카테고리, 가격대, 무료취소 | top_picks / lowest_price / highest_rating |

그 밖에: 체크아웃 폼(항공 8·호텔 11·렌터카 14개 입력 필드), HelpPage(검색창 + 카테고리별 아티클),
예약 관리(상태 필터 + 수정·취소), 정보 페이지 25종, 국가→지역→도시→숙소유형 계층 탐색.

### 판정에 직결되는 구조적 사실

**정렬은 항공·렌터카·호텔 세 도메인 모두 URL에 실리지 않는다**(React state). 검색 조건만 URL에 실린다.

이는 치팅 방지에 유리하다. 원본 `1704f00f`은 `filterCriteria_sortBy=PRICE`가 URL에 있어 주소창에
파라미터를 넣기만 해도 통과하지만, travelhub에서는 **정렬 컨트롤을 실제로 클릭해야만** 상태가 바뀐다.
대신 채점은 URL이 아니라 DOM(선택된 정렬 컨트롤 + 결과 순서)으로 해야 한다.

## 커버 20개

### A. 여행 도메인 직접 (7)

| 태스크 | 원본이 하는 일 | travelhub 대응 |
|---|---|---|
| `fc6d8143` | delta.com에서 JFK→ORD 내일 항공편 검색. 결과의 출발·도착·날짜 표기 확인 | 항공 검색폼 → `originCode`/`destCode`/`depart` |
| `82bc8d6a` | qatarairways.com에서 뭄바이→스톡홀름 다음 월요일 조회. URL의 `fromStation`/`toStation`/`departing` 확인 | 동일 |
| `f79439ad` | ryanair.com에서 더블린→비엔나 편도, 성인 2명. URL의 `isReturn=false`/`tpAdults=2` 확인 | `tripType=one-way`·`adults=2` |
| `6c4c23a1` | delta.com에서 시애틀→뉴욕 검색 후 "마일" 탭으로 전환 | 마일 개념 없음 → 조건을 `direct`/`cabin` 필터로 치환 |
| `1704f00f` | rentalcars.com에서 취리히 픽업/반납, 대형차 필터, 가격순 정렬 | 차종 `Large` + `Price (lowest first)` |
| `47543840` | budget.com에서 보스턴 로건 픽업, 다음달 10~11일, 좌석수 정렬 | 좌석수 정렬 없음 → 가격/평점 정렬로 치환 |
| `b7895e80` | tripadvisor.com에서 뉴욕 호텔, 성인 2, 다음 주말, 최저가 정렬 후 결과 페이지 유지 | `Lowest price first` |

### B. 검색 → 다중 필터 → 정렬 (5)

| 태스크 | 원본이 하는 일 | travelhub 대응 |
|---|---|---|
| `2888b4e6` | macys.com에서 남성→셔츠→사이즈 L→반팔→할인 50% 이상, 패싯 5개를 겹쳐 적용. 채점은 적용된 필터 상태 | 호텔: 성급·리뷰점수·숙소유형·가격대 체크박스 중첩 |
| `82279c77` | cars.com에서 전기차 + 5만 달러 이하 + 우편번호 10001 반경 50마일. URL의 `fuel_slugs=electric`·`list_price_max`·`maximum_distance` 확인 | **렌터카 연료 `Electric` 체크박스 실재** + 가격 상한 + 픽업 위치. 5개 중 가장 근접 |
| `9f3f70fc` | nba.com에서 여성→나이키→저지 카테고리 진입 후 $60 초과 가격대. URL에 `women`/`nike`/`jerseys` 포함돼야 함 | 숙소유형·도시가 URL에 실리는 계층 검색 + 가격 필터 |
| `cabb3bae` | kohls.com에서 "spider-man toys for kids" 검색 후 "Price Low-High" 정렬. 본문에 정렬 라벨이 보이면 통과 | 검색 + `Lowest price first` — 정렬 라벨이 DOM에 노출되는 구조까지 동일 |
| `7f52cab9` | Google Shopping에서 "drip coffee maker" 검색 후 세일 + $25~60 + 블랙 3중 필터, 결과 페이지 이탈 금지 | 검색어 URL 반영 + 다중 필터 + 결과 페이지 유지 |

### C. 검색·탐색 → 상세 페이지 도달 (6)

원본 6개 모두 "정보 사이트에서 특정 페이지까지 찾아 들어가기"이고 채점은 최종 URL 또는 본문 텍스트다.

| 태스크 | 원본이 하는 일 | travelhub 대응 |
|---|---|---|
| `b070486d` | drugs.com에서 타미플루 검색 → 약품 상세 → 부작용 하위 페이지/앵커까지 | HelpPage 검색창 → 아티클 상세 (검색→상세 2단계 동일) |
| `0d8b7de3` | drugs.com 메뉴에서 천연물 데이터베이스 섹션(`/npc/` 또는 `/npp/`)을 찾아 진입 | 푸터/헤더 정보 섹션 계층 (About·Sustainability·Trust & Safety·Investors 등 25종) |
| `9f935cce` | justice.gov 부서 계층을 따라 Civil Division의 문서·양식 목록까지 | Help 카테고리("Manage your booking", "Payment & receipts" 등) → 아티클 목록 |
| `a728a36e` | dmv.virginia.gov에서 `licenses-ids → license → applying → eligibility` 4단계 계층 탐색 | 국가 → 지역 → 도시 → 숙소유형 계층 페이지 |
| `f0b971a1` | nfl.com에서 2019 시즌 슈퍼볼 경기를 찾아 점수(31-20)를 화면에 띄움 | 항공편/호텔 상세에서 특정 수치 확인 |
| `f3b19d1e` | ticketek에서 티켓 배송 관련 FAQ 페이지를 찾아 도달 | HelpPage에 배송·결제·취소 카테고리 아티클 실재 |

### D. 폼 입력 / 목록에서 최댓값 선택 (2)

| 태스크 | 원본이 하는 일 | travelhub 대응 |
|---|---|---|
| `da46d875` | mbta.com 예약 시스템에서 8개월 뒤 첫 월요일, 오전 9~12시 슬롯 선택 → 이름(James Smith)·이메일 입력 → **"book" 버튼은 누르지 않고 대기** | 체크아웃 폼 + 달력 날짜 선택. "결제 직전까지만" 조건이 그대로 성립 |
| `a96b564e` | FlightAware 포럼 General 카테고리로 이동 → 답글 수가 가장 많은 스레드를 찾아 엶 | 호텔 목록 `Top reviewed` 정렬 + 카드의 `N reviews` 표기 → 최다 항목 열기 |

## 조건부 2개

- **`b4f95342`** — recreation.gov에서 "Diamond" 캠핑장의 **Next Available(다음 예약 가능일)** 조회.
  채점이 가용성 테이블의 특정 컬럼을 읽는다. travelhub는 사용자가 날짜를 지정하면 결과를 주는
  구조라 "가장 빠른 가능일을 시스템이 제시하는" 화면이 없다. 궤적의 핵심(가용성 표 읽기)이 빠진다.
- **`121ba48f`** — Steam에서 Dota 2를 찾아 DLC를 전부 장바구니에 담기. `/api/cart`는 있으나
  담기 버튼이 UI에 없다(소스에 주석만). 여러 항목을 누적하는 궤적이 화면에 없다.

## 불가 24개

- **브라우저 태스크 20개** — Chrome 설정(다크모드·폰트·검색엔진·언어·안전브라우징·자동삭제),
  북마크, 방문기록 삭제, PDF 저장, 바탕화면 바로가기, 확장프로그램 설치, 쿠키 삭제 등.
  웹사이트로 재현할 수 있는 종류가 아니다.
- `368d9ba4` 맨체스터 월간 날씨 예보 — 날씨 개념 없음
- `f5d96daf` 아이폰 3종 스펙 비교 테이블 — 나란히 비교하는 UI 없음
- `c1fa57f3` United 수하물 요금 계산기 — 정적 표기(`1 x 7kg`)만 있고 계산 입력 흐름 없음
- `59155008` "carl과 비슷한 이름" 검색 — 해당 없음

## 태스크 저술 전 처리해야 할 것

- **데이터 시딩이 A그룹 7개 전부에 필요하다.** 기본 상태가 아시아·유럽 중심이라 원본 지명이
  하나도 없다.
  - 공항 18개: `HKG LHR LGW STN JFK LAX NRT HND CDG SIN DXB SYD PEK PVG ICN BKK FRA AMS`
    — ORD·BOM·ARN·DUB·VIE·SEA 없음
  - 항공편 8편, 렌터카 **3대**(Economy/Luxury/SUV; 지점 LHR/JFK/LAX/HKG/CDG/DXB/SIN)
    — 취리히·보스턴 없고 `Large` 차종 데이터가 0대다(UI 필터에는 있는데 매칭될 차가 없음)
  - 호텔 23개(London/Paris/Edinburgh/Manchester/Tokyo 등) — 뉴욕 없음
  - `PATCH /api/state`로 주입 가능하므로 훅 작성 문제이지 앱 수정 문제는 아니다
- **자동화 차단 가드 패치가 선행돼야 한다.** `Router.tsx`의 `disable-devtool`이 CDP 연결을 감지하면
  `window.location.replace('https://www.google.com')`으로 페이지를 통째로 날린다. Playwright는
  CDP로 붙으므로 로드 2~7초 후 이탈한다. `window.location`은 unforgeable이라 훅으로 못 막고,
  소스 패치만이 해결책이다.
- **진행 플래그가 이미 앱에 계측돼 있다.** `src/app/api/task052/`에 `ad-closed`, `open-hotel`,
  `open-checkout`, `click-session`, `flow` 엔드포인트가 있다(광고 모달 닫기 → 호텔 열기 → 체크아웃
  진입). 중간 보상(reward shaping)을 붙일 때 DOM 파싱 없이 그대로 읽을 수 있다.
- 정렬을 요구하는 태스크(`1704f00f` `b7895e80` `cabb3bae`)는 URL이 아니라 DOM으로 채점한다.

## 이 판정의 한계

"궤적이 같으면 전이된다"는 아직 가설이다. travelhub에서 학습한 정책이 OSWorld 평가에서 실제로
오르는지는 실험으로 확인해야 한다. 특히 B·C 그룹은 도메인이 완전히 다르므로(쇼핑몰 → 여행,
의약품 DB → 고객센터) 전이 폭이 A 그룹보다 좁을 수 있다.
