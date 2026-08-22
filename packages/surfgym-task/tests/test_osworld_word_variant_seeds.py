from pathlib import Path

from surfgym_task.io import SeedReader

SEEDS_DIR = (
    Path(__file__).parents[1] / "src" / "surfgym_task" / "data" / "word" / "seeds"
)

EXPECTED_VARIANTS = {
    "osworld_ecc2413d_insert_field_brief_page_break": {
        "initial": {
            "spec": {"kind": "body", "property": "text"},
            "value": (
                "FIELD VISIT BRIEF\n"
                "Complete the site walk before noon.\n"
                "PHOTO LOG\n"
                "Attach the approved photos."
            ),
        },
        "final": {
            "spec": {"kind": "body", "property": "textWithPageBreak"},
            "value": (
                "FIELD VISIT BRIEF\n"
                "Complete the site walk before noon.\n"
                "\fPHOTO LOG\n"
                "Attach the approved photos."
            ),
        },
    },
    "osworld_0e47de2a_request_bottom_left_page_numbers": {
        "initial": {
            "spec": {"kind": "body", "property": "textWithPageBreak"},
            "value": (
                "QUARTERLY FIELD REPORT\n"
                "Page one summary.\n"
                "\fAPPENDIX\n"
                "Page two notes."
            ),
        },
        "final": {
            "spec": {"kind": "pageNumber", "property": "request"},
            "value": {
                "location": "footer",
                "alignment": "left",
                "applyTo": "all",
                "startAt": 1,
            },
        },
    },
    "osworld_0a0faba3_request_end_tab_stop": {
        "initial": {
            "spec": {"kind": "body", "property": "text"},
            "value": "NORTH FIELD TEAM Monday afternoon",
        },
        "final": {
            "spec": {"kind": "tabStop", "property": "request"},
            "value": {
                "alignment": "end",
                "offset": 6,
                "paragraphIndexes": [0],
                "range": {"startOffset": 0, "endOffset": 33},
            },
        },
    },
    "osworld_6ada715d_request_inline_screenshot": {
        "initial": {
            "spec": {"kind": "body", "property": "text"},
            "value": (
                "CLASS SCHEDULE\n"
                "Insert the screenshot below this line.\n"
                "END"
            ),
        },
        "final": {
            "spec": {"kind": "image", "property": "request"},
            "value": {
                "assetId": "1.png",
                "anchor": "inline",
                "insertionOffset": 54,
            },
        },
    },
    "osworld_adf5e2c3_request_reference_and_cross_reference": {
        "initial": {
            "spec": {"kind": "body", "property": "text"},
            "value": (
                "ESSAY NOTES\n"
                "Paragraph one.\n"
                "Paragraph two.\n"
                "Paragraph three.\n"
                "Paragraph four cites <add here>.\n"
                "REFERENCES"
            ),
        },
        "final": {
            "spec": {"kind": "reference", "property": "history"},
            "value": [
                {
                    "sequence": 1,
                    "type": "addReference",
                    "refId": "ref-1",
                    "citation": (
                        "Steinberg, F. M., Bearden, M. M., & Keen, C. L. "
                        "(2003). Cocoa and chocolate flavonoids: Implications "
                        "for cardiovascular health. Journal of the American "
                        "Dietetic Association, 103(2), 215-223. doi: "
                        "10.1053/jada.2003.50028"
                    ),
                },
                {
                    "sequence": 2,
                    "type": "insertCrossReference",
                    "refId": "ref-1",
                    "display": "number",
                    "range": {"startOffset": 80, "endOffset": 90},
                },
            ],
        },
    },
    "osworld_4bcb1253_request_pdf_export": {
        "initial": {
            "spec": {"kind": "body", "property": "text"},
            "value": (
                "ORGANIZATIONAL SUMMARY\n"
                "Review the current reporting structure before distribution."
            ),
        },
        "final": {
            "spec": {"kind": "document", "property": "pdfExportRequest"},
            "value": {
                "format": "pdf",
                "fileName": "View_Person_Organizational_Summary.pdf",
            },
        },
    },
}


def test_osworld_word_variants_parse_with_exact_supported_atom_contracts() -> None:
    variants = {
        name: seed
        for seed, name in SeedReader(SEEDS_DIR).get_seed()
        if name in EXPECTED_VARIANTS
    }

    assert variants.keys() == EXPECTED_VARIANTS.keys()
    for name, expected in EXPECTED_VARIANTS.items():
        seed = variants[name]
        assert seed.domain == "word"
        assert seed.website == "http://localhost:3000/word"
        assert seed.accumulation == "CUMULATIVE"
        assert len(seed.states) == 2
        assert [
            {"spec": atom.spec, "value": atom.value}
            for atom in seed.states[0].atoms
        ] == [
            expected["initial"]
        ]
        assert [
            {"spec": atom.spec, "value": atom.value}
            for atom in seed.states[1].atoms
        ] == [
            expected["final"]
        ]
