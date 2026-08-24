import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

DATA_ROOT = Path(__file__).parents[1] / "src" / "surfgym_task" / "data"
WORKSPACE_ROOT = Path(__file__).parents[4]
FIXTURE_ROOT = WORKSPACE_ROOT / "surfgym-docker-served-fixture" / "src" / "docker_control" / "fixture"
OSWORLD_EXAMPLES_ROOT = WORKSPACE_ROOT / "OSWorld" / "evaluation_examples" / "examples"
SOURCE_DOMAINS = {"word": "libreoffice_writer", "gimp": "gimp", "vlc": "vlc", "web": "chrome"}
SEMANTIC_STEM = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
ALLOWED_TOP_LEVEL = {"instruction", "website", "evaluation", "states"}
FORBIDDEN_TOP_LEVEL = {
    "id", "uuid", "provenance", "domain", "empty_start", "accumulation",
    "goal", "end", "criteria",
}


@dataclass(frozen=True)
class TransformationExpectation:
    domain: str
    old_stem: str
    source_id: str
    new_stem: str
    instruction: str
    website: str | dict[str, object]
    initial_atoms: list[dict[str, object]] | None
    provenance_assets: Sequence[str]
    cua_boundary: str


EXPECTED_TRANSFORMATIONS = (
    TransformationExpectation(
        "word", "bb8ccc78-479f-4a2f-a71e-d565e439436b",
        "bb8ccc78-479f-4a2f-a71e-d565e439436b", "start_live_coauthoring_for_incident_brief",
        "The incident-response brief is ready. Invite Mina Park and Devon Lee into a live coauthoring session so all three of us can edit this same document simultaneously and see one another’s changes as they type.",
        "http://localhost:3000/word",
        [{"spec": {"kind": "body", "property": "text"}, "value": "INCIDENT RESPONSE BRIEF\nStatus: monitoring\nOwners: Mina Park, Devon Lee, and Operations\nNext review: 16:30"}],
        (),
        "No functional invite, presence, synchronization, or multi-user live-edit workflow; reject a local single-user edit.",
    ),
    TransformationExpectation(
        "gimp", "osworld_045bf3ff_convert_image_cmyk", "045bf3ff-9077-4b86-b483-a1040a949cff",
        "convert_exhibit_photo_to_true_cmyk",
        "Prepare the opened Seoul exhibit photograph for four-color press by changing the document itself to a true CMYK color model—not a soft proof or an RGB export—and keep the picture content unchanged.",
        {"base": "http://localhost:53001/gimp", "setup_files": [{"source": "Landscape-Seoul.jpg", "target": "desktop"}], "open_file": "Landscape-Seoul.jpg"},
        None, ("gate.jpeg",),
        "No true CMYK document model; reject soft proof and RGB export.",
    ),
    TransformationExpectation(
        "gimp", "osworld_2e6f678f_batch_brightness", "2e6f678f-472d-4c55-99cc-8e7c5c402a71",
        "batch_brighten_destination_photos",
        "Prepare the three destination-scouting photos on the Desktop in one GIMP batch: add 35 brightness to Landscape-Nature.jpg, Landscape-Seoul.jpg, and Landscape-Swiss.jpg without opening and editing them one by one, and write `nature_review.jpg`, `seoul_review.jpg`, and `swiss_review.jpg`.",
        {"base": "http://localhost:53001/gimp", "setup_files": [{"source": "Landscape-Nature.jpg", "target": "desktop"}, {"source": "Landscape-Seoul.jpg", "target": "desktop"}, {"source": "Landscape-Swiss.jpg", "target": "desktop"}]},
        None, ("squirrel.jpeg", "panda.jpeg", "heron.jpeg"),
        "No one-step multi-file brightness-plus-three-export workflow; reject editing one image.",
    ),
    TransformationExpectation(
        "gimp", "osworld_38f48d40_trim_video", "38f48d40-764e-4e77-a7cf-51dfce880291",
        "trim_museum_walkthrough_clip",
        "Use GIMP to extract only 00:01 through 00:03 from the Desktop file `fullvideo.mp4` for a museum lobby loop, and export that segment as `lobby_loop.mp4`.",
        {"base": "http://localhost:53001/gimp", "setup_files": [{"source": "fullvideo.mp4", "target": "desktop"}]},
        None, ("fullvideo.mp4",),
        "No editable video timeline plus MP4 segment export; reject a still-frame import.",
    ),
    TransformationExpectation(
        "gimp", "osworld_58d3eeeb_translate_hidden_audio", "58d3eeeb-e9d0-499f-962e-fd0db2a744d8",
        "translate_imagined_audio_from_landscape",
        "The opened landscape image is said to contain a spoken evacuation announcement hidden in its pixels. Recover that recording, translate the speech into Spanish, and place the translation in a new GIMP text layer.",
        {"base": "http://localhost:53001/gimp", "setup_files": [{"source": "Landscape-Nature.jpg", "target": "desktop"}], "open_file": "Landscape-Nature.jpg"},
        None, ("heron.jpeg",),
        "No recoverable audio, playback, transcription, or translation source; reject invented Spanish text.",
    ),
    TransformationExpectation(
        "gimp", "osworld_5ca86c6f_download_hku_logo", "5ca86c6f-f317-49d8-b6a7-b527541caae8",
        "fetch_reykjavik_crest_inside_gimp",
        "Without opening a browser or another app, use only GIMP to find the official Reykjavík city crest on the municipality’s website and save it to the Desktop as a transparent PNG named `reykjavik_crest.png`.",
        {"base": "http://localhost:53001/gimp"}, None, (),
        "No municipal-site web search/navigation/download workflow; reject a fabricated crest or browser use.",
    ),
    TransformationExpectation(
        "gimp", "osworld_62f7fd55_convert_logo_svg", "62f7fd55-0687-4a43-b6e1-3eda16fc6252",
        "vectorize_rock_badge_as_svg",
        "Turn the opened rock badge artwork into editable vector paths and save a true SVG named `rock_badge.svg`; embedding or wrapping the original raster pixels in an SVG does not count.",
        {"base": "http://localhost:53001/gimp", "setup_files": [{"source": "rock.png", "target": "desktop"}], "open_file": "rock.png"},
        None, ("logo.png",),
        "No automatic editable vector-path conversion; reject raster pixels wrapped in SVG.",
    ),
    TransformationExpectation(
        "gimp", "osworld_8ea73f6f_upscale_without_size_growth", "8ea73f6f-9689-42ad-8c60-195bbf06a7ba",
        "restore_subject_detail_without_size_growth",
        "Create a four-times-larger-pixel version of the opened subject photo that genuinely restores missing fine detail, and save it as `subject_restored.jpg` without making the output file even one byte larger than the input.",
        {"base": "http://localhost:53001/gimp", "setup_files": [{"source": "subject.jpg", "target": "desktop"}], "open_file": "subject.jpg"},
        None, ("low_resolution.jpeg",),
        "Resampling cannot guarantee restored detail plus no byte growth; reject ordinary upscale/export.",
    ),
    TransformationExpectation(
        "gimp", "osworld_e19bd559_reduce_photo_brightness", "e19bd559-633b-4b02-940f-d946248f088e",
        "dim_absent_harbor_sunset_photo",
        "Open `Harbor-Sunset.jpg` from the Desktop, lower its brightness by 20, and save the adjusted copy as `Harbor-Sunset-dim.jpg`.",
        {"base": "http://localhost:53001/gimp"}, None, (),
        "The exact named input is absent; reject Dark.jpg and brightness-menu evidence alone.",
    ),
    TransformationExpectation(
        "gimp", "osworld_fbb548ca_set_blue_theme", "fbb548ca-c2a6-4601-9204-e39a2efc507b",
        "set_gimp_coral_application_theme",
        "Change all of GIMP’s application chrome—menus, docks, and dialogs—to a built-in color theme named `Coral`, and leave the image canvas content unchanged.",
        {"base": "http://localhost:53001/gimp"}, None, (),
        "Preferences lacks Coral; reject icon-theme and canvas-color changes.",
    ),
    TransformationExpectation(
        "vlc", "osworld_7882ed6e_play_google_drm_content", "7882ed6e-bece-4bf0-bada-c32dc1ddae72",
        "play_cinemacloud_drm_rental",
        "Play my purchased CinemaCloud rental `Northern Lights — Season 2` directly in VLC while keeping its store DRM protection enabled; do not replace it with an unprotected local copy.",
        {"base": "http://localhost:53001/vlc"}, None, (),
        "No CinemaCloud source, account, license, or protected rental; reject a local substitute.",
    ),
    TransformationExpectation(
        "vlc", "osworld_cb130f0d_adapt_to_room_lighting", "cb130f0d-d36f-4302-9838-b3baf46139b6",
        "auto_match_lake_video_to_ambient_light",
        "While `lake.mp4` plays on the visitor kiosk, continuously sense the room’s light level and automatically adapt the video brightness and contrast whenever the ambient lighting changes.",
        {"base": "http://localhost:53001/vlc", "setup_files": [{"source": "lake.mp4", "target": "desktop"}], "open_file": "lake.mp4"},
        None, (),
        "No ambient sensor or continuous adaptive mode; reject fixed manual brightness/contrast.",
    ),
    TransformationExpectation(
        "web", "osworld_3720f614_set_xenothian_language", "3720f614-37fd-4d04-8a6b-76f54f8c222d",
        "switch_travelhub_to_arabic",
        "Use TravelHub’s own language selector to change the travel site interface to Arabic and leave Arabic selected for future searches.",
        "http://localhost:3200/", None, (),
        "No Arabic locale or rendered UI; reject a raw hidden language preference.",
    ),
    TransformationExpectation(
        "web", "osworld_ae78f875_set_search_results_50", "ae78f875-5b98-4907-bbb5-9c737fc68c03",
        "set_hotel_results_page_size_fifty",
        "For this Rome hotel search, show exactly 50 hotel cards on each results page and save 50 as the default page size for future TravelHub hotel searches.",
        {"base": "http://localhost:3200/search", "param": {"destination": "Rome", "adults": "2"}},
        None, (),
        "No user-facing page-size or persistent control; reject response metadata.",
    ),
)

EXCLUDED_NON_INFEASIBLE_SEEDS = (
    ("gimp", "osworld_dbbf4b99_convert_raw_to_jpeg"),
    ("vlc", "osworld_5ac2891a_disable_play_and_exit"),
    ("web", "osworld_93eabf48_disable_chrome_dark_mode"),
)


def test_transformation_expectation_mapping_is_complete_and_unique() -> None:
    assert len(EXPECTED_TRANSFORMATIONS) == 14
    assert len({case.source_id for case in EXPECTED_TRANSFORMATIONS}) == 14
    assert len({case.new_stem for case in EXPECTED_TRANSFORMATIONS}) == 14
    assert {
        domain: sum(case.domain == domain for case in EXPECTED_TRANSFORMATIONS)
        for domain in ("word", "gimp", "vlc", "web")
    } == {"word": 1, "gimp": 9, "vlc": 2, "web": 2}
    assert all(case.cua_boundary.strip() for case in EXPECTED_TRANSFORMATIONS)


@pytest.mark.parametrize("case", EXPECTED_TRANSFORMATIONS, ids=lambda case: f"{case.domain}-{case.new_stem}")
def test_transformed_infeasible_seed_matches_frozen_contract(case: TransformationExpectation) -> None:
    old_seed_path = DATA_ROOT / case.domain / "seeds" / f"{case.old_stem}.json"
    active_seed_path = DATA_ROOT / case.domain / "seeds" / f"{case.new_stem}.json"
    assert old_seed_path.exists() is False
    assert active_seed_path.is_file()
    assert SEMANTIC_STEM.fullmatch(case.new_stem)
    assert not case.new_stem.startswith("osworld_")
    assert case.source_id[:8] not in case.new_stem

    payload = json.loads(active_seed_path.read_text(encoding="utf-8"))
    assert payload["instruction"] == case.instruction
    assert payload["website"] == case.website
    assert payload["evaluation"] == {"mode": "infeasible"}
    assert set(payload) <= ALLOWED_TOP_LEVEL
    assert set(payload).isdisjoint(FORBIDDEN_TOP_LEVEL)
    if case.initial_atoms is None:
        assert "states" not in payload
    else:
        assert payload["states"] == [case.initial_atoms]

    original_path = OSWORLD_EXAMPLES_ROOT / SOURCE_DOMAINS[case.domain] / f"{case.source_id}.json"
    reference_dir = DATA_ROOT / case.domain / "reference" / case.new_stem
    reference_path = reference_dir / f"{case.source_id}.json"
    assert original_path.is_file()
    assert reference_path.read_bytes() == original_path.read_bytes()
    original = json.loads(original_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    assert reference["id"] == original["id"] == case.source_id
    assert reference["instruction"] == original["instruction"]
    assert payload["instruction"] != original["instruction"]

    if case.domain == "word":
        unavailable_path = reference_dir / "source-asset-unavailable.json"
        assert json.loads(unavailable_path.read_text(encoding="utf-8")) == {
            "source_asset": "The Wonders of Our Solar System.docx",
            "source_url": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/libreoffice_writer/bb8ccc78-479f-4a2f-a71e-d565e439436b/The%20Wonders%20of%20Our%20Solar%20System.docx",
            "status": "unavailable",
            "reason": "The source asset is unavailable in the current worktree and sibling fixture; the active seed uses embedded incident-brief state and does not depend on this file.",
        }
        assert not (reference_dir / "The Wonders of Our Solar System.docx").exists()
        assert not (reference_dir / "source-asset.json").exists()
        assert not (DATA_ROOT / "word" / "reference" / f"{case.source_id}.json").exists()
        expected_entries = {reference_path.name, unavailable_path.name}
    else:
        expected_entries = {reference_path.name, *case.provenance_assets}
        for asset in case.provenance_assets:
            assert (reference_dir / asset).read_bytes() == (FIXTURE_ROOT / case.domain / asset).read_bytes()
    assert {path.name for path in reference_dir.iterdir()} == expected_entries

    website = payload["website"]
    if isinstance(website, dict):
        setup_files = website.get("setup_files", [])
        staged_sources = [item["source"] for item in setup_files]
        assert all(item == {"source": item["source"], "target": "desktop"} for item in setup_files)
        if case.domain in {"gimp", "vlc"}:
            assert all((FIXTURE_ROOT / case.domain / source).is_file() for source in staged_sources)
        assert website.get("open_file") is None or website["open_file"] in staged_sources


def test_positive_boundaries_remain_supported_and_absent_inputs_stay_absent() -> None:
    assert not (FIXTURE_ROOT / "gimp" / "Harbor-Sunset.jpg").exists()
    assert not (FIXTURE_ROOT / "gimp" / "reykjavik_crest.png").exists()
    for seed_path in (DATA_ROOT / "gimp" / "seeds").glob("*.json"):
        website = json.loads(seed_path.read_text(encoding="utf-8"))["website"]
        setup_files = website.get("setup_files", []) if isinstance(website, dict) else []
        setup_sources = {item["source"] for item in setup_files}
        assert "Harbor-Sunset.jpg" not in setup_sources
        assert "reykjavik_crest.png" not in setup_sources
    brighten = json.loads((DATA_ROOT / "gimp" / "seeds" / "brighten_photo.json").read_text(encoding="utf-8"))
    assert brighten["evaluation"]["mode"] == "llm"
    assert brighten["website"]["open_file"] == "Dark.jpg"
    for stem in ("grayscale_mode", "indexed_color_mode", "scale_image_800x600", "icon_theme_legacy"):
        positive = json.loads((DATA_ROOT / "gimp" / "seeds" / f"{stem}.json").read_text(encoding="utf-8"))
        assert positive.get("evaluation", {}).get("mode") != "infeasible"
    vlc_positive = json.loads((DATA_ROOT / "vlc" / "seeds" / "boost_saturation.json").read_text(encoding="utf-8"))
    assert vlc_positive.get("evaluation", {}).get("mode") != "infeasible"
    french = json.loads((DATA_ROOT / "web" / "seeds" / "language_switch_french.json").read_text(encoding="utf-8"))
    assert french["states"][-1][0]["value"] == "fr"
    hotel_positive = json.loads((DATA_ROOT / "web" / "seeds" / "hotel_price_sort.json").read_text(encoding="utf-8"))
    assert hotel_positive.get("evaluation", {}).get("mode") != "infeasible"


def test_non_infeasible_originals_do_not_have_infeasible_source_seeds() -> None:
    for domain, name in EXCLUDED_NON_INFEASIBLE_SEEDS:
        assert not (DATA_ROOT / domain / "seeds" / f"{name}.json").exists()
