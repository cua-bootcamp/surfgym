import json
from pathlib import Path

import pytest
from surfgym_task.io import SeedReader
from surfgym_task.seed import InfeasibleSeedTask

DATA_ROOT = Path(__file__).parents[1] / "src" / "surfgym_task" / "data"
FIXTURE_ROOT = (
    Path(__file__).parents[4]
    / "surfgym-docker-served-fixture"
    / "src"
    / "docker_control"
    / "fixture"
)

EXPECTED_SEEDS = (
    ("gimp", "045bf3ff-9077-4b86-b483-a1040a949cff", "osworld_045bf3ff_convert_image_cmyk"),
    ("gimp", "2e6f678f-472d-4c55-99cc-8e7c5c402a71", "osworld_2e6f678f_batch_brightness"),
    ("gimp", "38f48d40-764e-4e77-a7cf-51dfce880291", "osworld_38f48d40_trim_video"),
    ("gimp", "58d3eeeb-e9d0-499f-962e-fd0db2a744d8", "osworld_58d3eeeb_translate_hidden_audio"),
    ("gimp", "5ca86c6f-f317-49d8-b6a7-b527541caae8", "osworld_5ca86c6f_download_hku_logo"),
    ("gimp", "62f7fd55-0687-4a43-b6e1-3eda16fc6252", "osworld_62f7fd55_convert_logo_svg"),
    ("gimp", "8ea73f6f-9689-42ad-8c60-195bbf06a7ba", "osworld_8ea73f6f_upscale_without_size_growth"),
    ("gimp", "e19bd559-633b-4b02-940f-d946248f088e", "osworld_e19bd559_reduce_photo_brightness"),
    ("gimp", "fbb548ca-c2a6-4601-9204-e39a2efc507b", "osworld_fbb548ca_set_blue_theme"),
    ("vlc", "7882ed6e-bece-4bf0-bada-c32dc1ddae72", "osworld_7882ed6e_play_google_drm_content"),
    ("vlc", "cb130f0d-d36f-4302-9838-b3baf46139b6", "osworld_cb130f0d_adapt_to_room_lighting"),
    ("web", "3720f614-37fd-4d04-8a6b-76f54f8c222d", "osworld_3720f614_set_xenothian_language"),
    ("web", "ae78f875-5b98-4907-bbb5-9c737fc68c03", "osworld_ae78f875_set_search_results_50"),
)

GIMP_SETUP_EXPECTATIONS = {
    "osworld_045bf3ff_convert_image_cmyk": (["gate.jpeg"], "gate.jpeg"),
    "osworld_2e6f678f_batch_brightness": (
        ["squirrel.jpeg", "panda.jpeg", "heron.jpeg"],
        None,
    ),
    "osworld_38f48d40_trim_video": (["fullvideo.mp4"], None),
    "osworld_58d3eeeb_translate_hidden_audio": (["heron.jpeg"], "heron.jpeg"),
    "osworld_62f7fd55_convert_logo_svg": (["logo.png"], None),
    "osworld_8ea73f6f_upscale_without_size_growth": (
        ["low_resolution.jpeg"],
        "low_resolution.jpeg",
    ),
}

EXCLUDED_NON_INFEASIBLE_SEEDS = (
    ("gimp", "osworld_dbbf4b99_convert_raw_to_jpeg"),
    ("vlc", "osworld_5ac2891a_disable_play_and_exit"),
    ("web", "osworld_93eabf48_disable_chrome_dark_mode"),
)


def _parsed_seeds(domain: str) -> dict[str, InfeasibleSeedTask]:
    return {
        name: seed
        for seed, name in SeedReader(DATA_ROOT / domain / "seeds").get_seed()
        if isinstance(seed, InfeasibleSeedTask)
    }


def test_original_infeasible_seed_coverage_is_complete_and_source_only() -> None:
    assert len(EXPECTED_SEEDS) == 13
    assert len({osworld_id for _domain, osworld_id, _name in EXPECTED_SEEDS}) == 13

    for domain, osworld_id, name in EXPECTED_SEEDS:
        seed_path = DATA_ROOT / domain / "seeds" / f"{name}.json"
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        seed = _parsed_seeds(domain)[name]

        assert name.startswith(f"osworld_{osworld_id[:8]}_")
        assert seed.domain == domain
        assert seed.evaluation.mode == "infeasible"
        assert seed.states is None or len(seed.states) == 1
        assert "states" not in payload
        assert {"id", "uuid", "provenance"}.isdisjoint(payload)


def test_gimp_setup_matches_original_inputs_and_fixture_assets() -> None:
    for name, (expected_sources, expected_open_file) in GIMP_SETUP_EXPECTATIONS.items():
        payload = json.loads(
            (DATA_ROOT / "gimp" / "seeds" / f"{name}.json").read_text(
                encoding="utf-8"
            )
        )
        website = payload["website"]

        assert [item["source"] for item in website["setup_files"]] == expected_sources
        assert {item["target"] for item in website["setup_files"]} == {"desktop"}
        assert website.get("open_file") == expected_open_file
        assert all(
            (FIXTURE_ROOT / "gimp" / source).is_file()
            for source in expected_sources
        )


def test_non_infeasible_originals_do_not_have_infeasible_source_seeds() -> None:
    for domain, name in EXCLUDED_NON_INFEASIBLE_SEEDS:
        assert not (DATA_ROOT / domain / "seeds" / f"{name}.json").exists()


@pytest.mark.parametrize("domain", ("gimp", "vlc", "web"))
def test_original_infeasible_seeds_convert_in_memory_without_augmentation(
    domain: str,
) -> None:
    expected_names = {
        name for expected_domain, _osworld_id, name in EXPECTED_SEEDS if expected_domain == domain
    }
    parsed = _parsed_seeds(domain)

    assert expected_names <= set(parsed)
    assert all(parsed[name].states is None for name in expected_names)
