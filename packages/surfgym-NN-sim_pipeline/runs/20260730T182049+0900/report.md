# Similarity run 20260730T092049Z

2026-07-30T09:42:36.666208+00:00 | models: uae-large-v1, bge-large-en-v1.5, gte-large | device: cpu

## 결론

- 평가 문항 89개 × 모델 3종에서 **플래그 2건** 발생. `data/contamination.csv`를 확인하세요.
- 플래그의 의미: 어떤 평가 문항에 대해, 그 문항을 의도적으로 말만 바꿔 쓴 것만큼이나 가까운 무언가가 학습셋에 있다는 뜻입니다. 0건이면 평가 문항이 학습셋에 다시 쓰인 적이 없다는 의미입니다.

## 1. 척도 — 네 기준 집합의 중앙값

네 열 모두 **top-1 코사인의 중앙값**입니다. 왼쪽 항목마다 오른쪽 집합 전체와
비교해 최댓값을 취하고, 그 최댓값들의 중앙값입니다. 왼쪽에서 오른쪽으로 갈수록
'더 닮은 관계'가 되며, OURS가 그 사이 어디에 놓이는지가 판정 내용입니다.

| model | domain | n | med<br>different app | med<br>same app,<br>diff task | **med<br>OURS** | med<br>same task,<br>reworded |
|---|---|---:|---:|---:|---:|---:|
| bge-large-en-v1.5 | chrome | 22 | 0.538 | 0.661 | **0.668** | 0.977 |
| bge-large-en-v1.5 | gimp | 18 | 0.662 | 0.732 | **0.843** | 0.977 |
| bge-large-en-v1.5 | vlc | 15 | 0.642 | 0.709 | **0.803** | 0.986 |
| gte-large | chrome | 22 | 0.774 | 0.842 | **0.858** | 0.992 |
| gte-large | gimp | 18 | 0.823 | 0.860 | **0.914** | 0.988 |
| gte-large | vlc | 15 | 0.821 | 0.865 | **0.909** | 0.993 |
| uae-large-v1 | chrome | 22 | 0.479 | 0.607 | **0.631** | 0.980 |
| uae-large-v1 | gimp | 18 | 0.619 | 0.692 | **0.807** | 0.976 |
| uae-large-v1 | vlc | 15 | 0.592 | 0.698 | **0.774** | 0.986 |

## 2. OURS 분포의 지표

§1의 OURS 열을 만든 분포(top-1 값 n개)의 지표와, 그 분포가 하한에 대해
얼마나 큰지(AUC)입니다. **절대값은 모델 간 비교 불가**이고(모델마다 바닥값이
다름), 비교 가능한 것은 AUC 열입니다.

| model | domain | n | median | max | p90 | p95 | p99 | AUC<br>vs lower |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| bge-large-en-v1.5 | chrome | 22 | 0.668 | 0.847 | -- | -- | -- | 0.580 |
| bge-large-en-v1.5 | gimp | 18 | 0.843 | 0.915 | -- | -- | -- | 0.838 |
| bge-large-en-v1.5 | vlc | 15 | 0.803 | 0.910 | -- | -- | -- | 0.835 |
| gte-large | chrome | 22 | 0.858 | 0.923 | -- | -- | -- | 0.708 |
| gte-large | gimp | 18 | 0.914 | 0.974 | -- | -- | -- | 0.831 |
| gte-large | vlc | 15 | 0.909 | 0.952 | -- | -- | -- | 0.898 |
| uae-large-v1 | chrome | 22 | 0.631 | 0.825 | -- | -- | -- | 0.650 |
| uae-large-v1 | gimp | 18 | 0.807 | 0.904 | -- | -- | -- | 0.827 |
| uae-large-v1 | vlc | 15 | 0.774 | 0.905 | -- | -- | -- | 0.824 |

- `AUC vs lower` — 우리 값 하나가 하한 값 하나보다 클 확률. 0.5면 구별 불가
- 상한(패러프레이즈) 분포와의 AUC는 전 도메인 0.994 이상으로 사실상 완전 분리이므로 열로 싣지 않습니다

## 3. 오염 검사 (평가 문항 축)

OSWorld 평가 문항 각각에 대해 학습셋에서 가장 가까운 이웃을 찾은 결과입니다.
§1·§2와 집계 축이 반대입니다 — 누수는 '평가 문항이 뚫렸는가'를 묻기 때문입니다.
판단 근거는 max와 플래그 개수이며 중앙값은 쓰지 않습니다. 평가 문항 하나만
뚫려도 문제라, 안심시키는 중앙값은 정작 중요한 꼬리에 대해 아무 말도 안 해줍니다.

| model | domain | eval items | max sim | flag threshold | flagged |
|---|---|---:|---:|---:|---:|
| bge-large-en-v1.5 | chrome | 46 | 0.847 | 0.901 | **0** |
| bge-large-en-v1.5 | gimp | 26 | 0.915 | 0.938 | **0** |
| bge-large-en-v1.5 | vlc | 17 | 0.910 | 0.966 | **0** |
| gte-large | chrome | 46 | 0.923 | 0.958 | **0** |
| gte-large | gimp | 26 | 0.974 | 0.959 | **2** |
| gte-large | vlc | 17 | 0.952 | 0.977 | **0** |
| uae-large-v1 | chrome | 46 | 0.825 | 0.868 | **0** |
| uae-large-v1 | gimp | 26 | 0.904 | 0.933 | **0** |
| uae-large-v1 | vlc | 17 | 0.905 | 0.966 | **0** |

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
| 0.974 | -- | gimp | Set the minimum number of undo steps to 50. | Set the minimum number of undo steps to 100. |
| 0.964 | -- | gimp | Can you shift the text box to the right? I keep accidentally selecting | Can you assist me in moving the text box to the left side? I keep acci |
| 0.952 | -- | vlc | Help me modify the folder used to store my recordings to my Videos fol | Help me modify the folder used to store my recordings to Desktop |
| 0.947 | -- | gimp | Could you fill the background layer with red color, leaving the object | Could you fill the background layer with green color, leaving the obje |
| 0.947 | -- | gimp | Could you brighten up my photo a bit? | Could you tone down the brightness of my photo? |
| 0.944 | -- | vlc | Can you set VLC to always start in fullscreen mode? | Can you enable fullscreen mode in VLC so that the video fill up the wh |
| 0.942 | -- | gimp | Could you export my photo to the desktop and name it "output.png"? | Could you assist me in placing my photo on the desktop and renaming it |
| 0.939 | -- | gimp | Please flip my figure vertically. | Please rotate my figure to mirror it horizontally. |
| 0.932 | -- | gimp | I'd like to soften the picture — could you assist me in lowering the c | I'd like to make the picture's contrast stronger to really bring out t |
| 0.923 | -- | chrome | Find a large car in Geneva and sort the results by lowest price. | Find a large car from next Monday to Friday in Zurich, sorted by price |
| 0.922 | -- | vlc | Can you change the color of the volume slider controller to red? | Can you change the color of the volume slider to black-ish color? I of |
| 0.921 | -- | chrome | Search for a one-way flight from Amsterdam to Rome for 2 adults on the | Search for a one way flight from Dublin to Vienna on 10th next month f |

## 5. 읽을 때 주의할 점

- **`data/metrics.csv`의 빈 백분위 칸은 의도된 것입니다.** 표본이 최소 크기에 못 미치면 백분위는 max에 이름만 바꾼 값이 되므로, 숫자를 찍는 대신 비웁니다. 최소 표본: p90는 n>=30, p95는 n>=50, p99는 n>=100. 현재 코퍼스 규모에서는 대부분의 도메인 행이 median과 max만 채워집니다.
- **절대 임계값(0.9 등)은 쓰지 않습니다.** 같은 앱의 무관한 지시문 두 개도 이미 높은 점수가 나오고 그 바닥값이 모델마다 다르기 때문에, 코사인 원값 자체로는 아무것도 판단할 수 없습니다. 판정은 §1에서 두 기준선(lower/upper) 사이 어디에 있는지와, §2의 AUC로 합니다.
- **중복 판정의 기준선은 'same app, different task'입니다.** 그게 비교 대상으로 타당한 집단이기 때문입니다. 'different app'은 척도가 어떻게 생겼는지 보여주고 모델 간 비교를 가능하게 하려고 함께 싣는 것이며, 판정 기준이 아닙니다.
- **이 파이프라인은 스크리닝 도구입니다.** 정답 수준의 중복 여부는 텍스트가 아니라 평가식으로 판정해야 하며, 여기서 걸러진 쌍을 사람이 확인하는 것까지가 한 묶음입니다.

## 6. 출처 (재현 정보)

- OSWorld: `https://github.com/xlang-ai/OSWorld.git` @ `b7db4d8c85d9e95e0b1db44de5bec954cf37f0cf`
- uae-large-v1: `WhereIsAI/UAE-Large-V1` @ `9c9b2c999b3350cfb3171ed429320668e39b00b8`
- bge-large-en-v1.5: `BAAI/bge-large-en-v1.5` @ `d4aa6901d3a41ba39fb536a557fa166f842b0e09`
- gte-large: `thenlper/gte-large` @ `4bef63f39fcc5e2d6b0aae83089f307af4970164`
- 패러프레이즈: claude-sonnet-5 (manual) / prompt v1-manual-1x / 2026-07-29T16:53:17.223789+00:00
- 도메인 매핑: `{'gimp': 'gimp', 'vlc': 'vlc', 'travel-ad-hub': 'chrome'}`
- 파이프라인 버전: 0.1.0
- 입력 파일 해시와 전체 설정: `data/manifest.json`
