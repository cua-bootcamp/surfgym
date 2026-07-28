# spreadsheet task 만들기

## 목표

[reference](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/data/spreadsheet/reference/) 안에 존재하는 osworld spreadsheet task를 비슷한 task로 뽑기

방법론은 다음과 같다.

## 1. Task Imitating

- [annual_change_rate](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/data/spreadsheet/reference/annual_change_rate/) 
- [calculate_column_sum](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/data/spreadsheet/reference/calculate_column_sum/) 
- [calculate_hired_year](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/data/spreadsheet/reference/calculate_hired_year/) 

위의 폴더를 보고 같은 형태를 만들어 내는 것이 목표다. 그 과정은 아래와 같다.

1. reference 디렉토리 안의 .json 파일들 중 변환을 목표로 하는 task를 하나 잡는다. `A.json` 이라고 가정하자. (실제는 task_id로 된 코드 일 것이다.)
2. `A.json`를 읽고 작업 내용은 완전히 동일하지만 cell data나 주제만 다른 식으로 task를 변경할 주제를 잡는다.
3. 새롭게 만들 task의 이름을 `B`라고 했을 때 `B` 디렉토리 안에 `A.json`을 넣고 `A.json` 내에서 사용하는 libreoffice file을 다운 받는다. _gold 형식으로 끝나는 libreoffice file도 있다면 다운받는다.
4. gold 파일이 있다면 해당 gold 파일을 복사해서 `B_gold.xslx`라고 이름 짓고 정답까지 포함한 내용을 넣는다.

## 2. Seed Task Generation

- [seeds_ready](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/data/spreadsheet/seeds_ready/) 내부에 이미 만들어진 seed들을 참고한다.

1. [seeds](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/data/spreadsheet/seeds/)에 `B.json`을 만든다.
2. `B.json`의 instruction 과 state를 붙이는데 이때 `state`는 [surfgym_task](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-task/src/surfgym_task/)  와 [spreadsheet](/Users/goonco/01_workspace/09_llm-lab/cua-boot/surfgym/packages/surfgym-fixture/src/surfgym_fixture/src/spreadsheet/) 의 내용을 자세히 보고 만들어야 한다.
3. 또한 instruction 생성 시에 기존 seed와 너무 동일하지 않게 (목적은 같되 벡터 유사도는 피할 수 있게) 만든다.
4. 이때 현재 spreadsheet fixture에서 evaluation이 불가능한 경우가 있다. (피봇 테이블, 차트) 이 경우 사용자에게 알린다.