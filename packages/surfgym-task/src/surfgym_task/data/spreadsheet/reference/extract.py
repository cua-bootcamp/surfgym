#!/usr/bin/env python3

import argparse
import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


def to_json_value(value: Any) -> Any:
    """Excel 셀 값을 JSON으로 직렬화 가능한 형태로 변환한다."""
    if value is None:
        return None

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def make_entry(
    sheet_name: str,
    coordinate: str,
    property_name: str,
    value: Any,
) -> dict[str, Any]:
    return {
        "spec": {
            "kind": "cell",
            "sheet": sheet_name,
            "cell": coordinate,
            "property": property_name,
        },
        "value": to_json_value(value),
    }


def extract_cells(workbook_path: Path) -> list[dict[str, Any]]:
    # 수식 자체를 읽는 workbook
    formula_workbook = load_workbook(
        workbook_path,
        data_only=False,
        read_only=False,
    )

    # 수식의 저장된 계산 결과를 읽는 workbook
    value_workbook = load_workbook(
        workbook_path,
        data_only=True,
        read_only=False,
    )

    entries: list[dict[str, Any]] = []

    for formula_sheet in formula_workbook.worksheets:
        sheet_name = formula_sheet.title
        value_sheet = value_workbook[sheet_name]

        for row in formula_sheet.iter_rows():
            for formula_cell in row:
                coordinate = formula_cell.coordinate
                raw_value = formula_cell.value

                # 완전히 비어 있는 셀은 제외한다.
                if raw_value is None:
                    continue

                if formula_cell.data_type == "f":
                    # 수식 문자열
                    # entries.append(
                    #     make_entry(
                    #         sheet_name=sheet_name,
                    #         coordinate=coordinate,
                    #         property_name="formula",
                    #         value=raw_value,
                    #     )
                    # )

                    # 해당 수식의 저장된 계산 결과
                    entries.append(
                        make_entry(
                            sheet_name=sheet_name,
                            coordinate=coordinate,
                            property_name="value",
                            value=value_sheet[coordinate].value,
                        )
                    )
                else:
                    entries.append(
                        make_entry(
                            sheet_name=sheet_name,
                            coordinate=coordinate,
                            property_name="value",
                            value=raw_value,
                        )
                    )

    formula_workbook.close()
    value_workbook.close()

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="XLSX 파일의 셀 값과 수식을 JSON 배열로 추출합니다."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="입력 XLSX/XLSM 파일",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="출력 JSON 파일. 생략하면 입력 파일명_cells.json을 사용합니다.",
    )
    args = parser.parse_args()

    input_path: Path = args.input

    if not input_path.exists():
        raise FileNotFoundError(f"파일이 없습니다: {input_path}")

    output_path = args.output or input_path.with_name(f"{input_path.stem}_cells.json")

    entries = extract_cells(input_path)

    output_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"추출한 항목: {len(entries)}개")
    print(f"출력 파일: {output_path.resolve()}")


if __name__ == "__main__":
    main()
