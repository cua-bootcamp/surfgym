# Similarity run 20260731T202838+0900

2026-07-31T20:52:43.493435+09:00 | models: uae-large-v1, bge-large-en-v1.5, gte-large | device: cpu

## 결론

- 평가 문항 89개 × 모델 3종에서 **플래그 5건** 발생. `data/contamination.csv`를 확인하세요.
- 플래그의 의미: 어떤 평가 문항에 대해, 그 문항을 의도적으로 말만 바꿔 쓴 것만큼이나 가까운 무언가가 학습셋에 있다는 뜻입니다. 0건이면 평가 문항이 학습셋에 다시 쓰인 적이 없다는 의미입니다.

## 1. 척도 — 네 기준 집합의 중앙값

네 열 모두 **top-1 코사인의 중앙값**입니다. 왼쪽 항목마다 오른쪽 집합 전체와
비교해 최댓값을 취하고, 그 최댓값들의 중앙값입니다. 왼쪽에서 오른쪽으로 갈수록
'더 닮은 관계'가 되며, OURS가 그 사이 어디에 놓이는지가 판정 내용입니다.

| model | domain | n | med<br>different app | med<br>same app,<br>diff task | **med<br>OURS** | med<br>same task,<br>reworded |
|---|---|---:|---:|---:|---:|---:|
| bge-large-en-v1.5 | chrome | 36 | 0.538 | 0.661 | **0.649** | 0.915 |
| bge-large-en-v1.5 | gimp | 55 | 0.662 | 0.732 | **0.727** | 0.951 |
| bge-large-en-v1.5 | vlc | 48 | 0.642 | 0.709 | **0.694** | 0.896 |
| gte-large | chrome | 36 | 0.774 | 0.842 | **0.844** | 0.967 |
| gte-large | gimp | 55 | 0.823 | 0.861 | **0.857** | 0.972 |
| gte-large | vlc | 48 | 0.821 | 0.865 | **0.866** | 0.956 |
| uae-large-v1 | chrome | 36 | 0.479 | 0.607 | **0.614** | 0.921 |
| uae-large-v1 | gimp | 55 | 0.619 | 0.692 | **0.693** | 0.950 |
| uae-large-v1 | vlc | 48 | 0.592 | 0.698 | **0.679** | 0.902 |

## 2. OURS 분포의 지표

§1의 OURS 열을 만든 분포(top-1 값 n개)의 지표와, 그 분포가 하한에 대해
얼마나 큰지(AUC)입니다. **절대값은 모델 간 비교 불가**이고(모델마다 바닥값이
다름), 비교 가능한 것은 AUC 열입니다.

| model | domain | n | median | max | p90 | p95 | p99 | AUC<br>vs lower |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| bge-large-en-v1.5 | chrome | 36 | 0.649 | 0.847 | 0.761 | -- | -- | 0.497 |
| bge-large-en-v1.5 | gimp | 55 | 0.727 | 0.897 | 0.834 | 0.858 | -- | 0.473 |
| bge-large-en-v1.5 | vlc | 48 | 0.694 | 0.846 | 0.785 | -- | -- | 0.484 |
| gte-large | chrome | 36 | 0.844 | 0.920 | 0.891 | -- | -- | 0.634 |
| gte-large | gimp | 55 | 0.857 | 0.946 | 0.913 | 0.933 | -- | 0.489 |
| gte-large | vlc | 48 | 0.866 | 0.923 | 0.904 | -- | -- | 0.534 |
| uae-large-v1 | chrome | 36 | 0.614 | 0.825 | 0.722 | -- | -- | 0.566 |
| uae-large-v1 | gimp | 55 | 0.693 | 0.885 | 0.818 | 0.836 | -- | 0.497 |
| uae-large-v1 | vlc | 48 | 0.679 | 0.832 | 0.793 | -- | -- | 0.498 |

- `AUC vs lower` — 우리 값 하나가 하한 값 하나보다 클 확률. 0.5면 구별 불가
- 상한(패러프레이즈) 분포와의 AUC는 전 도메인 0.998 이상으로 사실상 완전 분리이므로 열로 싣지 않습니다

## 3. 오염 검사 (평가 문항 축)

OSWorld 평가 문항 각각에 대해 학습셋에서 가장 가까운 이웃을 찾은 결과입니다.
§1·§2와 집계 축이 반대입니다 — 누수는 '평가 문항이 뚫렸는가'를 묻기 때문입니다.
판단 근거는 max와 플래그 개수이며 중앙값은 쓰지 않습니다. 평가 문항 하나만
뚫려도 문제라, 안심시키는 중앙값은 정작 중요한 꼬리에 대해 아무 말도 안 해줍니다.

| model | domain | eval items | max sim | flag threshold | flagged |
|---|---|---:|---:|---:|---:|
| bge-large-en-v1.5 | chrome | 46 | 0.847 | 0.801 | **2** |
| bge-large-en-v1.5 | gimp | 26 | 0.897 | 0.908 | **0** |
| bge-large-en-v1.5 | vlc | 17 | 0.846 | 0.838 | **2** |
| gte-large | chrome | 46 | 0.920 | 0.927 | **0** |
| gte-large | gimp | 26 | 0.946 | 0.955 | **0** |
| gte-large | vlc | 17 | 0.923 | 0.932 | **0** |
| uae-large-v1 | chrome | 46 | 0.825 | 0.817 | **1** |
| uae-large-v1 | gimp | 26 | 0.885 | 0.910 | **0** |
| uae-large-v1 | vlc | 17 | 0.832 | 0.863 | **0** |

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
| 0.946 | 0.39 | gimp | My photo needs to end up on the desktop under the name "output.png" —  | Could you assist me in placing my photo on the desktop and renaming it |
| 0.946 | 0.46 | gimp | The interface is too dark to work in — switch GIMP over to the Light t | Please help change GIMP's theme from dark to light. |
| 0.943 | 0.71 | gimp | This photo came out too dark — could you punch up the brightness a lit | Could you tone down the brightness of my photo? |
| 0.929 | 0.43 | gimp | The text box sits too close to the image layer underneath and I keep g | Can you assist me in moving the text box to the left side? I keep acci |
| 0.923 | 0.45 | vlc | I'd like the volume slider recolored to red — can you do that? | Can you change the color of the volume slider to black-ish color? I of |
| 0.920 | 0.40 | chrome | Find a hotel in Rome for 3 adults, sort the results by lowest price, a | Find a Hotel in New York City with lowest price possible for 2 adults  |
| 0.918 | 0.58 | gimp | In GIMP's preferences, bump the undo history's minimum step count up t | Set the minimum number of undo steps to 100. |
| 0.916 | 0.76 | vlc | Whenever I open VLC I want it to launch already in fullscreen — can yo | Can you enable fullscreen mode in VLC so that the video fill up the wh |
| 0.914 | 0.93 | gimp | Could you assist me in reducing the color saturation of my photo by -5 | Could you tone down the brightness of my photo? |
| 0.913 | 0.59 | vlc | Bump VLC's maximum volume cap up to 150% of the normal level. | I like watching movies (using VLC) on my laptop and sometimes the volu |
| 0.912 | 0.90 | vlc | Make VLC automatically pause playback whenever I minimize the window. | Enable VLC Minimal Interface in window mode so the bottom playback con |
| 0.912 | 0.47 | gimp | Add a new layer for me and give it the name 'new layer'. | Could you assist me in adding a new layer and naming it 'Square'? |

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
- 패러프레이즈: gemini-3.6-flash / prompt v2-multi-5x / 2026-07-31T17:08:17+09:00
- 도메인 매핑: `{'gimp': 'gimp', 'vlc': 'vlc', 'travel-ad-hub': 'chrome'}`
- 파이프라인 버전: 0.1.0
- 입력 파일 해시와 전체 설정: `data/manifest.json`
