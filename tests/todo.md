# TODO

1. 테스트 코드를 위해 소스 코드를 고치지 않기. (이를테면 이전에 Transport 주입 방식 변경)
2. 테스트 코드는 내부에서 서버 실행까지 같이 넣어서 pytest 명령어로 쉽게 테스트 할 수 있게하기


## instances: 1, contexts_per_instance: 1 test

1. Success Scenario
2. OutOfInstance Scenario
3. Allocate Failure Scenario

## instances: 1, contexts_per_instance: 4 test

1. Sequential Success Scenario
2. OutofInstance Scenario
3. Partial Release & Reallocate

## instances: 4, contexts_per_instance: 1 test

1. Sequential Success Scenario
2. OutofInstance Scenario
3. Partial Release & Reallocate
