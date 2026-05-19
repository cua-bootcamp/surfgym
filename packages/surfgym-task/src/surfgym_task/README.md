1. rule_test.js 전부 콘솔창에 복붙

2.

```js
allinone([{
                    "selector": "pre[class*='_Code_']",
                    "target": "text",
                    "value": "/assets/wallpapers/abstract-mesh-gradient-orange-red-purple.png",
                    "match": "contains"
                },....])
```

이런식으로 콘솔창에 `allinone` 함수와 rule 배열 넣고 1 이면 성공 0 이면 실패.


### ProzillaOS scripts

1. 창 제목 뽑기

```js
(() => {
  const titiles = [
    ...document.querySelectorAll("p[class*='ProzillaOS-WindowTitle']")
  ].find((el) => el.textContent.trim() === "고치세요");
  return titiles?.innerText ?? "";
})();
// 있으면 "고치세요" 없으면 ""
``` 

```json
{
  "script": "(() => {\n  const titiles = [\n    ...document.querySelectorAll(\"p[class*='ProzillaOS-WindowTitle']\")\n  ].find((el) => el.textContent.trim() === \"고치세요\");\n  return titiles?.innerText ?? \"\";\n})();"
}
```

2. 창 제목 확인 후 그안에 내용 뽑기 

다음예시는 prozilla_task_A_01 를 베이스로 생성
```js
(() => {
  const titleElement = [
    ...document.querySelectorAll("p[class*='ProzillaOS-WindowTitle']")
  ].find((el) => el.textContent.trim() === "desktop.xml (preview) - Notes");

  if (titleElement) {
    const windowView = titleElement.closest(".ProzillaOS-WindowView");

    if (windowView) {
      const code = [...windowView.querySelectorAll("code")].find((el) =>
        el.innerText.includes(
          "/assets/wallpapers/abstract-mesh-gradient-orange-red-purple.png"
        )
      );

      return code?.innerText ?? "";
    }
  }
  return "";
})();
```

```json
{
  "script": "(() => {\n  const titleElement = [\n    ...document.querySelectorAll(\"p[class*='ProzillaOS-WindowTitle']\")\n  ].find((el) => el.textContent.trim() === \"desktop.xml (preview) - Notes\");\n\n  if (titleElement) {\n    const windowView = titleElement.closest(\".ProzillaOS-WindowView\");\n\n    if (windowView) {\n      const code = [...windowView.querySelectorAll(\"code\")].find((el) =>\n        el.innerText.includes(\n          \"/assets/wallpapers/abstract-mesh-gradient-orange-red-purple.png\"\n        )\n      );\n\n      return code?.innerText ?? \"\";\n    }\n  }\n  return \"\";\n})();"
}
```