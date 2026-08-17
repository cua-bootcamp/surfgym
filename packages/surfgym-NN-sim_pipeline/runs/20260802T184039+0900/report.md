# Similarity run 20260802T184039+0900

2026-08-02T18:40:54.232074+09:00 | models: potion-base-32m | device: cpu

## 결론

- 평가 문항 89개 × 모델 1종에서 **플래그 11건** 발생. `data/contamination.csv`를 확인하세요.
- 플래그의 의미: 어떤 평가 문항에 대해, 그 문항을 의도적으로 말만 바꿔 쓴 것만큼이나 가까운 무언가가 학습셋에 있다는 뜻입니다. 0건이면 평가 문항이 학습셋에 다시 쓰인 적이 없다는 의미입니다.

## 1. 척도 — 네 기준 집합의 중앙값

네 열 모두 **top-1 코사인의 중앙값**입니다. 왼쪽 항목마다 오른쪽 집합 전체와
비교해 최댓값을 취하고, 그 최댓값들의 중앙값입니다. 왼쪽에서 오른쪽으로 갈수록
'더 닮은 관계'가 되며, OURS가 그 사이 어디에 놓이는지가 판정 내용입니다.

| model | domain | n | med<br>different app | med<br>same app,<br>diff task | **med<br>OURS** | med<br>same task,<br>reworded |
|---|---|---:|---:|---:|---:|---:|
| potion-base-32m | chrome | 36 | 0.282 | 0.439 | **0.397** | 0.872 |
| potion-base-32m | gimp | 55 | 0.414 | 0.473 | **0.510** | 0.890 |
| potion-base-32m | vlc | 48 | 0.456 | 0.515 | **0.474** | 0.839 |

## 2. OURS 분포의 지표

§1의 OURS 열을 만든 분포(top-1 값 n개)의 지표와, 그 분포가 하한에 대해
얼마나 큰지(AUC)입니다. **절대값은 모델 간 비교 불가**이고(모델마다 바닥값이
다름), 비교 가능한 것은 AUC 열입니다.

| model | domain | n | median | max | p90 | p95 | p99 | AUC<br>vs lower | 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| potion-base-32m | chrome | 36 | 0.397 | 0.858 | 0.599 | -- | -- | 0.470 | [0.34, 0.61] |
| potion-base-32m | gimp | 55 | 0.510 | 0.792 | 0.707 | 0.740 | -- | 0.541 | [0.40, 0.68] |
| potion-base-32m | vlc | 48 | 0.474 | 0.775 | 0.629 | -- | -- | 0.401 | [0.27, 0.55] |

- `AUC vs lower` — 우리 값 하나가 하한 값 하나보다 클 확률. 0.5면 구별 불가
- **CI가 겹치면 차이를 주장하지 마세요.** n=15~46에서 폭이 ±0.15 수준이라 점추정 0.04 변동은 노이즈입니다. 부트스트랩 2000회·seed 0, 양쪽 표본 모두 재표본.
- 상한(패러프레이즈) 분포와의 AUC는 전 도메인 0.985 이상으로 사실상 완전 분리이므로 열로 싣지 않습니다

## 3. 오염 검사 (평가 문항 축)

OSWorld 평가 문항 각각에 대해 학습셋에서 가장 가까운 이웃을 찾은 결과입니다.
§1·§2와 집계 축이 반대입니다 — 누수는 '평가 문항이 뚫렸는가'를 묻기 때문입니다.
판단 근거는 max와 플래그 개수이며 중앙값은 쓰지 않습니다. 평가 문항 하나만
뚫려도 문제라, 안심시키는 중앙값은 정작 중요한 꼬리에 대해 아무 말도 안 해줍니다.

| model | domain | eval items | max sim | flag threshold | flagged |
|---|---|---:|---:|---:|---:|
| potion-base-32m | chrome | 46 | 0.858 | 0.666 | **1** |
| potion-base-32m | gimp | 26 | 0.792 | 0.670 | **9** |
| potion-base-32m | vlc | 17 | 0.775 | 0.723 | **1** |

### 3-1. 임계값 민감도

임계값은 패러프레이즈 점수의 순서통계량이라, `min`을 쓰면 89문항 중
**가장 어설픈 하나**가 게이트 전체를 정합니다. 실제로 생성기를 바꾸자 임계값이
−0.004~−0.128 움직였고, 태스크가 그대로인 채 플래그가 0 → 2로 바뀐 적이 있습니다.
아래 세 값이 같으면 판정이 그 하나에 의존하지 않는다는 뜻입니다.

| model | domain | flagged<br>@min | flagged<br>@p5 | flagged<br>@p10 |
|---|---|---:|---:|---:|
| potion-base-32m | chrome | 1 | 1 | 1 |
| potion-base-32m | gimp | 9 | 2 | 0 |
| potion-base-32m | vlc | 1 | 1 | 1 |

헤드라인 수치는 run1~3과 비교 가능하도록 `@min`을 그대로 씁니다.

### 3-2. 소진 / 미소진 코호트

OSWorld 항목을 **우리가 설계 소스로 쓴 것(소진)**과 **손대지 않은 것(미소진)**으로
나눈 값입니다. 소진 쪽 점수가 높은 건 설계대로이고 문서 조회로 해소됩니다 —
**행동이 필요한 건 미소진 쪽 max가 높을 때**이며, 그것이 의도치 않은 재파생입니다.
출처는 `data/exhausted_sources.json`.

| model | domain | 소진 n | 소진 med | 소진 max | 미소진 n | 미소진 med | **미소진 max** | AUC<br>소진>미소진 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| potion-base-32m | chrome | 22 | 0.409 | 0.858 | 24 | 0.238 | **0.392** | 0.799 |
| potion-base-32m | gimp | 18 | 0.665 | 0.792 | 8 | 0.515 | **0.600** | 0.889 |
| potion-base-32m | vlc | 15 | 0.586 | 0.775 | 2 | 0.525 | **0.553** | 0.633 |

- AUC가 0.5 부근이면 문서화된 파생이 유사도를 전혀 설명하지 못한다는 뜻입니다.

## 3-B. 어휘 중첩 (n-gram) — 표준 기법 병기

코사인과 독립된 채널입니다. 오염 검출 문헌의 관례는 13-gram 중첩(GPT-3 정의)이므로
같은 네 기준 집합에 그대로 적용했습니다. 값은 **왼쪽 항목 중 오른쪽 집합과
n-gram이 하나라도 겹치는 비율**(GPT-3 기준을 그대로 옮긴 이진 판정)입니다.

| domain | dataset | n | n=3 | n=4 | n=5 | n=8 | n=13 | undef<br>@n=13 | Jaccard<br>(uni+bi) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| chrome | different app | 46 | 0.261 | 0.130 | 0.065 | 0.000 | 0.000 | 13/46 | 0.070 |
| chrome | same app, different task | 46 | 0.543 | 0.152 | 0.043 | 0.000 | 0.000 | 13/46 | 0.127 |
| chrome | **OURS vs OSWorld** | 36 | 0.444 | 0.083 | 0.056 | 0.000 | 0.000 | 15/36 | 0.100 |
| chrome | same task, reworded | 230 | 0.878 | 0.665 | 0.461 | 0.142 | 0.061 | 65/230 | 0.333 |
| gimp | different app | 26 | 0.538 | 0.462 | 0.192 | 0.000 | 0.000 | 11/26 | 0.117 |
| gimp | same app, different task | 26 | 0.577 | 0.538 | 0.231 | 0.077 | 0.000 | 11/26 | 0.162 |
| gimp | **OURS vs OSWorld** | 55 | 0.345 | 0.127 | 0.091 | 0.019 | 0.000 | 15/55 | 0.121 |
| gimp | same task, reworded | 130 | 0.923 | 0.769 | 0.615 | 0.194 | 0.000 | 64/130 | 0.401 |
| vlc | different app | 17 | 0.647 | 0.294 | 0.118 | 0.000 | 0.000 | 2/17 | 0.122 |
| vlc | same app, different task | 17 | 0.471 | 0.118 | 0.000 | 0.000 | 0.000 | 2/17 | 0.110 |
| vlc | **OURS vs OSWorld** | 48 | 0.271 | 0.125 | 0.083 | 0.000 | 0.000 | 17/48 | 0.079 |
| vlc | same task, reworded | 85 | 0.800 | 0.612 | 0.388 | 0.094 | 0.071 | 15/85 | 0.228 |

`undef@n=13` — 그 항목이 13단어보다 짧아 n-gram을 만들 수조차 없는 수.
**검출률의 분모는 정의된 항목만**이며(짧은 항목은 분자·분모 양쪽에서 제외),
따라서 검출률이 0이라는 것은 '재보니 없었다'는 뜻이지 '못 쟀다'가 아닙니다.

- **`same task, reworded` 행이 이 표의 정답지입니다.** 설계상 의도적으로 말만 바꾼
  쌍이므로, 어떤 검출 기법이든 여기서 신호가 나와야 합니다.
- 그 행조차 n=13에서 검출률이 0 부근이면, 이 문장 길이에서 표준 기준은 **명백한
  복제조차 못 잡는다**는 뜻입니다. 우리 값이 0인 것은 그때 근거가 되지 못합니다.
- Jaccard(uni+bi) 열은 중앙값이며, 문장이 짧아도 항상 정의되는 대조군입니다.
- **집계 단위 주의** — `same task, reworded`의 n은 문항당 5변형을 각각 한 항목으로
  센 것입니다(코사인 채널은 `_median_by_task`로 문항당 1개로 접은 뒤 임계값을 냄).
  이진 검출률에는 median 접기가 정의되지 않아 변형 단위를 유지했습니다.
- 토큰화: lowercase; [a-z0-9]+ runs; no stopword removal; no stemming
- 짧은 쌍 처리: items too short to form an n-gram are excluded from both numerator and denominator of detection_rate, not scored 0; counted in n_undefined (`data/lexical.csv`의 `n_undefined`)
- 그림: `figures/lexical_sweep.png`

## 4. 사람이 직접 볼 쌍

점수가 높은 순입니다. **높은 점수는 판정이 아니라 두 문장을 읽어보라는 신호입니다** —
텍스트 유사도는 '베껴서 값만 바꾼 것'과 '독립적으로 만들었는데 같은 기능에 수렴한 것'을
구분하지 못합니다. 전체 목록은 `review.csv`에 있습니다.

`ratio`는 1등이 2등보다 얼마나 압도적인지입니다(거리 기준 d1/d2, Lowe 2004 §7.1).
**0에 가까우면 특정 하나만 유독 가까운 것**이고, 1에 가까우면 그 도메인 전체와
고만고만하게 닮은 것입니다. 점수가 같아도 성격이 반대일 수 있으므로,
**score가 높으면서 ratio가 낮은 행부터** 읽으면 됩니다.

표시된 점수는 그 쌍에 대해 여러 모델 중 가장 높은 값입니다.

| score | ratio | domain | ours | OSWorld |
|---:|---:|---|---|---|
| 0.858 | 0.29 | chrome | Find a hotel in Rome for 3 adults, sort the results by lowest price, a | Find a Hotel in New York City with lowest price possible for 2 adults  |
| 0.791 | 0.37 | gimp | Could you help me hide the dockable panels on the right side of the sc | Could you help me remove the dock on the left side of the screen in th |
| 0.775 | 0.55 | vlc | Make VLC automatically pause playback whenever I minimize the window. | Enable VLC Minimal Interface in window mode so the bottom playback con |
| 0.769 | 0.51 | gimp | The interface is too dark to work in — switch GIMP over to the Light t | Please help change GIMP's theme from dark to light. |
| 0.761 | 0.55 | chrome | Search for hotels in Lisbon and sort the results by lowest price. | Find a Hotel in New York City with lowest price possible for 2 adults  |
| 0.749 | 0.56 | gimp | Could you turn my image into Indexed color mode within GIMP? | Could you turn my image into CYMK mode within GIMP ? |
| 0.737 | 0.44 | gimp | I need the subject layer resized — set its height to 256 pixels and ke | Could you assist me with resizing the dog layer of an image? I need to |
| 0.721 | 0.42 | gimp | The text box sits too close to the image layer underneath and I keep g | Can you assist me in moving the text box to the left side? I keep acci |
| 0.708 | 0.42 | gimp | Help me open up the Gaussian Blur filter window. | Help me open up the Vignette filter window. |
| 0.706 | 0.64 | gimp | Add a new layer for me and give it the name 'new layer'. | Could you assist me in adding a new layer and naming it 'Square'? |
| 0.701 | 0.51 | gimp | The background layer needs to be solid red — fill it in, but don't tou | Could you fill the background layer with green color, leaving the obje |
| 0.697 | 0.58 | vlc | Stop VLC from showing the currently playing file name in the window ti | Enable VLC Minimal Interface in window mode so the bottom playback con |

## 5. 읽을 때 주의할 점

- **`data/metrics.csv`의 빈 백분위 칸은 의도된 것입니다.** 표본이 최소 크기에 못 미치면 백분위는 max에 이름만 바꾼 값이 되므로, 숫자를 찍는 대신 비웁니다. 최소 표본: p90는 n>=30, p95는 n>=50, p99는 n>=100. 현재 코퍼스 규모에서는 대부분의 도메인 행이 median과 max만 채워집니다.
- **절대 임계값(0.9 등)은 쓰지 않습니다.** 같은 앱의 무관한 지시문 두 개도 이미 높은 점수가 나오고 그 바닥값이 모델마다 다르기 때문에, 코사인 원값 자체로는 아무것도 판단할 수 없습니다. 판정은 §1에서 두 기준선(lower/upper) 사이 어디에 있는지와, §2의 AUC로 합니다.
- **중복 판정의 기준선은 'same app, different task'입니다.** 그게 비교 대상으로 타당한 집단이기 때문입니다. 'different app'은 척도가 어떻게 생겼는지 보여주고 모델 간 비교를 가능하게 하려고 함께 싣는 것이며, 판정 기준이 아닙니다.
- **이 파이프라인은 스크리닝 도구입니다.** 정답 수준의 중복 여부는 텍스트가 아니라 평가식으로 판정해야 하며, 여기서 걸러진 쌍을 사람이 확인하는 것까지가 한 묶음입니다.

## 6. 출처 (재현 정보)

- OSWorld: `https://github.com/xlang-ai/OSWorld.git` @ `b7db4d8c85d9e95e0b1db44de5bec954cf37f0cf`
- potion-base-32m: `minishlab/potion-base-32M` @ `1e5a03f8eeb2c98b928fbbd846f22f816360919f`
- 패러프레이즈: gemini-3.6-flash / prompt v2-multi-5x / 2026-07-31T17:08:17+09:00
- 도메인 매핑: `{'gimp': 'gimp', 'vlc': 'vlc', 'travel-ad-hub': 'chrome'}`
- 파이프라인 버전: 0.1.0
- 입력 파일 해시와 전체 설정: `data/manifest.json`
