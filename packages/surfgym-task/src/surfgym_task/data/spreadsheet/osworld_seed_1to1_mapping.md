# OSWorld reference ↔ spreadsheet seed 1:1 매핑

## 결론

- 검사 대상: `reference` 47개, `seeds` 176개
- `seeds` 구성: 기본 seed 63개, `_refine_*` 변형 109개, 차트 `복사본` 4개
- 엄격한 1:1 유지 권장: **25개**
- 유사하지만 순수한 1:1이 아니어서 보류/제외: **14개**
- 대응 seed 없음: **8개**
- 엄격 정리 시: seed 176개 중 아래 A 등급 25개만 유지하고 **151개 제외**

여기서 1:1은 데이터 값, 셀 주소, 도메인 명칭이 같다는 뜻이 아니라, **핵심 스프레드시트 조작과 산출물의 종류가 동일하다**는 뜻이다. 한 reference에 여러 seed가 걸릴 때는 `_refine_*`가 없는 기본형, `복사본`이 아닌 원본, 요구 단계가 가장 적은 seed 하나만 선택했다.

## A. 유지 권장 — 순수한 1:1 매핑

| # | OSWorld reference | 유지할 seed | 공통 핵심 동작 |
|---:|---|---|---|
| ✅ | `04d9aeaf-7bed-4024-bedb-e10e6f00eb7f`| | 여러 자산 열의 전년 대비 변화율 표 계산 |
| 2 | [`0a2e43bf-b26c-4631-a966-af9dfa12c9e5`](reference/0a2e43bf-b26c-4631-a966-af9dfa12c9e5.json) | [`calculate_monthly_total_sales.json`](seeds/calculate_monthly_total_sales.json) | 월별 합계 행 계산 후 선 차트 생성 |
| 3 | [`0bf05a7d-b28b-44d2-955a-50b41e24012a`](reference/0bf05a7d-b28b-44d2-955a-50b41e24012a.json) | [`padding_tag_codes.json`](seeds/padding_tag_codes.json) | 숫자 ID를 복사하고 앞쪽을 0으로 패딩 |
| 4 | [`12382c62-0cd1-4bf2-bdc8-1d20bf9b2371`](reference/12382c62-0cd1-4bf2-bdc8-1d20bf9b2371.json) | [`chart_sales_cogs_dashboard.json`](seeds/chart_sales_cogs_dashboard.json) | 새 시트에 Sales와 COGS 비교 열 차트 생성 |
| ✅ | [`1273e544-688f-496b-8d89-3e0f40aa0606`](reference/1273e544-688f-496b-8d89-3e0f40aa0606.json) | [`sheet_revenue_export_to_new_sheet.json`](seeds/sheet_revenue_export_to_new_sheet.json) | Revenue 헤더와 열을 새 시트로 복사 |
| 6 | [`1954cced-e748-45c4-9c26-9855b97fbc5e`](reference/1954cced-e748-45c4-9c26-9855b97fbc5e.json) | [`pivot_region_count_sheet2.json`](seeds/pivot_region_count_sheet2.json) | 새 시트의 피벗 테이블에서 범주별 레코드 수 집계 |
| 7 | [`26a8440e-c166-4c50-aef4-bfb77314b46b`](reference/26a8440e-c166-4c50-aef4-bfb77314b46b.json) | [`sheet2_monthly_formula_fill.json`](seeds/sheet2_monthly_formula_fill.json) | 새 시트에 월별 합계 요약표 작성 |
| 8 | [`347ef137-7eeb-4c80-a3bb-0951f26a8aff`](reference/347ef137-7eeb-4c80-a3bb-0951f26a8aff.json) | [`chart_two_year_3d_comparison.json`](seeds/chart_two_year_3d_comparison.json) | 두 연도의 데이터를 각각 별도 열 차트로 생성 |
| ✅ | [`357ef137-7eeb-4c80-a3bb-0951f26a8aff`](reference/357ef137-7eeb-4c80-a3bb-0951f26a8aff.json) | [`calculate_rental_fee.json`](seeds/calculate_rental_fee.json) | 시간 형식의 기간과 시간당 단가를 올바르게 곱함 |
| 10 | `37608790-6147-45d0-9f20-1137bb35703d`| ) | 한 필드의 이름 정보를 세 열로 분리 |
| 11 | [`3a7c8185-25c1-4941-bd7b-96e823c9f21f`](reference/3a7c8185-25c1-4941-bd7b-96e823c9f21f.json) | [`chart_sorted_time_series.json`](seeds/chart_sorted_time_series.json) | 날짜 오름차순 정렬 후 시계열 선 차트 생성 |
| 12 | [`4172ea6e-6b77-4edb-a9cc-c0014bd1603b`](reference/4172ea6e-6b77-4edb-a9cc-c0014bd1603b.json) | [`calculate_loan_maturity_date.json`](seeds/calculate_loan_maturity_date.json) | 대출 시작일과 기간으로 만기일 계산 |
| ✅ | [`42e0a640-4f19-4b28-973d-729602b5a4a7`](reference/42e0a640-4f19-4b28-973d-729602b5a4a7.json) | [`sheet_cross_sheet_total_summary.json`](seeds/sheet_cross_sheet_total_summary.json) | 새 시트에서 Revenue와 Expenses 합계 계산 |
| 14 | [`4de54231-e4b5-49e3-b2ba-61a0bec721c0`](reference/4de54231-e4b5-49e3-b2ba-61a0bec721c0.json) | [`fill_acceleration_and_concat_combined_data.json`](seeds/fill_acceleration_and_concat_combined_data.json) | 수식 채우기 후 헤더·값을 소수 둘째 자리 텍스트로 결합 |
| ✅ | [`4e6fcf72-daf3-439f-a232-c434ce416af6`](reference/4e6fcf72-daf3-439f-a232-c434ce416af6.json) | [`calculate_employee_age_from_birthdate.json`](seeds/calculate_employee_age_from_birthdate.json) | 생년월일로 직원 나이 계산 |
| 16 | [`51b11269-2ca8-4b2a-9163-f21758420e78`](reference/51b11269-2ca8-4b2a-9163-f21758420e78.json) | [`assending_amount.json`](seeds/assending_amount.json) | 금액 열을 기준으로 전체 레코드 오름차순 정렬 |
| 17 | [`6054afcb-5bab-4702-90a0-b259b5d3217c`](reference/6054afcb-5bab-4702-90a0-b259b5d3217c.json) | [`hide_tbd_row.json`](seeds/hide_tbd_row.json) | 임시 결측값이 있는 행을 삭제·필터 없이 숨김 |
| 18 | [`7a4e4bc8-922c-4c84-865c-25ba34136be1`](reference/7a4e4bc8-922c-4c84-865c-25ba34136be1.json) | [`reorder_columns_date_firstname_lastname_orderid_sales.json`](seeds/reorder_columns_date_firstname_lastname_orderid_sales.json) | Date, First Name, Last Name, Order ID, Sales 순으로 열 재배치 |
| 19 | [`7e429b8d-a3f0-4ed0-9b58-08957d00b127`](reference/7e429b8d-a3f0-4ed0-9b58-08957d00b127.json) | [`mangager_name_lookup.json`](seeds/mangager_name_lookup.json) | 범주-담당자 lookup 표로 담당자 이름 채우기 |
| 20 | [`a01fbce3-2793-461f-ab86-43680ccbae25`](reference/a01fbce3-2793-461f-ab86-43680ccbae25.json) | [`set_decimal_separator_comma.json`](seeds/set_decimal_separator_comma.json) | 소수 구분점을 점에서 쉼표로 변경 |
| 21 | [`a9f325aa-8c05-4e4f-8341-9e4358565f4f`](reference/a9f325aa-8c05-4e4f-8341-9e4358565f4f.json) | [`clean_book_titles_title_case.json`](seeds/clean_book_titles_title_case.json) | 제목을 복사하며 중복 공백 제거 및 Title Case 정규화 |
| 22 | [`abed40dc-063f-4598-8ba5-9fe749c0615d`](reference/abed40dc-063f-4598-8ba5-9fe749c0615d.json) | [`unique_departments.json`](seeds/unique_departments.json) | 최초 등장 순서를 유지한 고유값 목록 생성 |
| 23 | [`d681960f-7bc3-4286-9913-a8812ba3261a`](reference/d681960f-7bc3-4286-9913-a8812ba3261a.json) | [`classify_bmi_status.json`](seeds/classify_bmi_status.json) | 기준표에 따라 각 행의 등급/상태 분류 |
| 24 | [`eb03d19a-b88d-4de4-8a64-ca0ac66f426b`](reference/eb03d19a-b88d-4de4-8a64-ca0ac66f426b.json) | [`transpose_table_paste.json`](seeds/transpose_table_paste.json) | 지정 범위를 전치하여 다른 위치에 붙여넣기 |
| 25 | [`f9584479-3d0d-4c79-affa-9ad7afdd8850`](reference/f9584479-3d0d-4c79-affa-9ad7afdd8850.json) | [`calculate_total_and_grand_row.json`](seeds/calculate_total_and_grand_row.json) | 누락된 행·열 합계와 grand total 채우기 |

### A 등급 seed 정리 원칙

- 위 표의 기본 `.json` 하나만 유지한다.
- 같은 이름의 `_refine_*` 파일은 모두 제외한다.
- `chart_sales_cogs_dashboard`, `chart_sorted_time_series`, `chart_two_year_3d_comparison`의 `복사본`은 제외한다.
- 철자 오류가 있는 `assending_amount.json`, `mangager_name_lookup.json`도 현재 실제 파일명이므로 매핑에서는 그대로 사용한다.

## B. 유사하지만 제외 권장 — 순수한 1:1이 아님

아래는 가장 가까운 seed를 하나씩 골랐지만, 핵심 단계·산출 방식·적용 범위 중 하나 이상이 달라서 엄격한 유지 목록에는 넣지 않는다.

| OSWorld reference | 가장 가까운 seed | 제외 이유 |
|---|---|---|
| [`0326d92d-d218-48a8-9ca1-981cd6d064c7`](reference/0326d92d-d218-48a8-9ca1-981cd6d064c7.json) | [`create_total_growth_rates.json`](seeds/create_total_growth_rates.json) | reference는 월별 합계·성장률과 막대/선 차트 2개를 요구하지만 seed에는 차트가 없음 |
| [`035f41ba-6653-43ab-aa63-c86d449d62e5`](reference/035f41ba-6653-43ab-aa63-c86d449d62e5.json) | [`calculate_product_prices.json`](seeds/calculate_product_prices.json) | 산술 결과의 정수부를 ID와 결합하는 구조는 같지만 새 시트 출력이 없고 평균 계산이 추가됨 |
| [`0cecd4f3-74de-457b-ba94-29ad6b5dafb6`](reference/0cecd4f3-74de-457b-ba94-29ad6b5dafb6.json) | [`sheet_backup_copy_not_move.json`](seeds/sheet_backup_copy_not_move.json) | 시트 복사만 같고 원본/복사본/다른 시트 이름 변경과 순서 배치가 빠짐 |
| [`1de60575-bb6e-4c3d-9e6a-2fa699f9f197`](reference/1de60575-bb6e-4c3d-9e6a-2fa699f9f197.json) | [`pivot_promotion_summary_no_manual_values.json`](seeds/pivot_promotion_summary_no_manual_values.json) | promotion별 Revenue 피벗은 같지만 seed는 row 배치이며 Orders 합계도 추가함 |
| [`1e8df695-bd1b-45b3-b557-e7d599cf7597`](reference/1e8df695-bd1b-45b3-b557-e7d599cf7597.json) | [`calculate_profit_margin.json`](seeds/calculate_profit_margin.json) | reference는 `Sales-COGS`인 Profit, seed는 `Gross Profit/Sales`인 profit margin 계산 |
| [`21ab7b40-77c2-4ae6-8321-e00d3a086c73`](reference/21ab7b40-77c2-4ae6-8321-e00d3a086c73.json) | [`calculate_period_rate_percentage.json`](seeds/calculate_period_rate_percentage.json) | 기간 이자율 계산은 같지만 최댓값의 초록색 글꼴 강조가 빠짐 |
| [`21df9241-f8d7-4509-b7f1-37e501a823f7`](reference/21df9241-f8d7-4509-b7f1-37e501a823f7.json) | [`represent_values_in_thousands_and_millions.json`](seeds/represent_values_in_thousands_and_millions.json) | 단위 변환 구조는 같지만 M/B가 K/M으로 바뀌고 추가 산술 결과까지 요구함 |
| [`30e3e107-1cfb-46ee-a755-2cd080d7ba6a`](reference/30e3e107-1cfb-46ee-a755-2cd080d7ba6a.json) | [`create_demographic_proportion_summary_tables.json`](seeds/create_demographic_proportion_summary_tables.json) | demographic 비율은 같지만 피벗 3개·새 시트·병합·스타일이 일반 요약표 2개로 축소됨 |
| [`4f07fbe9-70de-4927-a4d5-bb28bc12c52c`](reference/4f07fbe9-70de-4927-a4d5-bb28bc12c52c.json) | [`fixed_decimal_values_in_text.json`](seeds/fixed_decimal_values_in_text.json) | reference는 텍스트 안의 숫자 표시를 고치지만 seed는 별도 숫자 셀의 반올림/서식만 수행 |
| [`51719eea-10bc-4246-a428-ac7c433dd4b3`](reference/51719eea-10bc-4246-a428-ac7c433dd4b3.json) | [`calculate_revenue_and_summarize.json`](seeds/calculate_revenue_and_summarize.json) | Revenue 계산은 같지만 reference의 product Pivot Table이 seed에서는 일반 요약표임 |
| [`535364ea-05bd-46ea-9937-9f55c68507e8`](reference/535364ea-05bd-46ea-9937-9f55c68507e8.json) | [`pivot_multi_summary_stacked.json`](seeds/pivot_multi_summary_stacked.json) | 피벗 2개와 차원은 같지만 product 피벗의 값이 Revenue가 아니라 Units임 |
| [`6e99a1ad-07d2-4b66-a1ce-ece6d99c20a5`](reference/6e99a1ad-07d2-4b66-a1ce-ece6d99c20a5.json) | [`format_spent_column_two_decimal_places.json`](seeds/format_spent_column_two_decimal_places.json) | reference는 원래 spent 열을 포맷하지만 seed는 새 Formatted 열을 만들고 값을 복사함 |
| [`7efeb4b1-3d19-4762-b163-63328d66303b`](reference/7efeb4b1-3d19-4762-b163-63328d66303b.json) | [`fill_employee_ids.json`](seeds/fill_employee_ids.json) | 둘 다 순번 채우기지만 reference는 `No. #` 텍스트 패턴, seed는 1000부터의 숫자 ID임 |
| [`8b1ce5f2-59d2-4dcc-b0b0-666a714b9a14`](reference/8b1ce5f2-59d2-4dcc-b0b0-666a714b9a14.json) | [`change_sunday_color.json`](seeds/change_sunday_color.json) | reference는 토·일 모두 빨간 배경, seed는 일요일만 처리 |

## C. 대응 seed 없음

| OSWorld reference | 필요한 동작 | 판정 |
|---|---|---|
| [`01b269ae-2111-4a07-81fd-3fcd711993b0`](reference/01b269ae-2111-4a07-81fd-3fcd711993b0.json) | 빈 셀을 바로 위 셀 값으로 채우기 | `fill_blank_cells_from_above.json`은 파일명과 달리 같은 행 날짜에서 연도를 추출하므로 대응 아님 |
| [`1334ca3e-f9e3-4db8-9ca7-b4c653be7d17`](reference/1334ca3e-f9e3-4db8-9ca7-b4c653be7d17.json) | 시트 줌아웃 | 관련 seed 없음 |
| [`1d17d234-e39d-4ed7-b46f-4417922a4e7c`](reference/1d17d234-e39d-4ed7-b46f-4417922a4e7c.json) | 새 시트 생성과 여러 범위 셀 병합 | 관련 seed 없음 |
| [`2bd59342-0664-4ccb-ba87-79379096cc08`](reference/2bd59342-0664-4ccb-ba87-79379096cc08.json) | 행별 sparkline 생성 | 관련 seed 없음 |
| [`3aaa4e37-dc91-482e-99af-132a612d40f3`](reference/3aaa4e37-dc91-482e-99af-132a612d40f3.json) | 현재 시트를 CSV로 내보내기 | 관련 seed 없음 |
| [`4188d3a4-077d-46b7-9c86-23e1a036f6c1`](reference/4188d3a4-077d-46b7-9c86-23e1a036f6c1.json) | 헤더 범위 고정 | 관련 seed 없음 |
| [`aa3a8974-2e85-438b-b29e-a64df44deb4b`](reference/aa3a8974-2e85-438b-b29e-a64df44deb4b.json) | 한 페이지 맞춤과 PDF 내보내기 | 관련 seed 없음 |
| [`ecb0df7a-4e8d-4a03-b162-053391d3afaf`](reference/ecb0df7a-4e8d-4a03-b162-053391d3afaf.json) | Pass/Fail/Held 데이터 유효성 드롭다운 | `recognize_pass_fail_held.json`은 점수로 값을 계산하는 task라서 대응 아님 |

## 최종 유지 목록

엄격하게 정리한다면 아래 25개만 남기는 것이 가장 안전하다.

```text
annual_change_rate.json
assending_amount.json
calculate_employee_age_from_birthdate.json
calculate_loan_maturity_date.json
calculate_monthly_total_sales.json
calculate_rental_fee.json
calculate_total_and_grand_row.json
chart_sales_cogs_dashboard.json
chart_sorted_time_series.json
chart_two_year_3d_comparison.json
classify_bmi_status.json
fill_acceleration_and_concat_combined_data.json
hide_tbd_row.json
mangager_name_lookup.json
name_split.json
padding_tag_codes.json
pivot_region_count_sheet2.json
reorder_columns_date_firstname_lastname_orderid_sales.json
set_decimal_separator_comma.json
sheet2_monthly_formula_fill.json
sheet_cross_sheet_total_summary.json
sheet_revenue_export_to_new_sheet.json
transpose_table_paste.json
unique_departments.json
clean_book_titles_title_case.json
```

## 정리 실행 전 확인 사항

1. `_refine_*` 109개는 모두 기본 seed의 변형이므로 1:1 목적에서는 제외한다.
2. `복사본` 4개는 원본과 중복이므로 제외한다.
3. B 등급 14개는 비슷하지만 요구사항이 달라 false positive가 될 수 있으므로 제외한다.
4. A 표에 없는 나머지 기본 seed도 현재 47개 reference와 직접 대응하지 않으므로 제외한다.
5. 이 문서는 분석 결과만 정리한 것이며 seed 파일 자체는 삭제하거나 수정하지 않았다.
