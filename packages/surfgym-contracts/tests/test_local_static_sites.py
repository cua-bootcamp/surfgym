from pathlib import PurePosixPath

from surfgym_contracts.local_static_sites import LOCAL_STATIC_SITES


def test_local_static_site_contract_is_narrow_complete_and_unique() -> None:
    assert len(LOCAL_STATIC_SITES) == 14
    assert {site.key for site in LOCAL_STATIC_SITES} == {
        "GITHUB",
        "GMAIL",
        "HUBSPOT",
        "INSTACART",
        "INSTAGRAM",
        "JIRA",
        "LINKEDIN",
        "MICROSOFT_TEAMS",
        "PINTEREST",
        "SHOPIFY_ADMIN",
        "STRIPE_DASHBOARD",
        "TRELLO",
        "TWITTER",
        "WECHAT",
    }
    assert len({site.port for site in LOCAL_STATIC_SITES}) == len(LOCAL_STATIC_SITES)
    assert {site.port for site in LOCAL_STATIC_SITES} == {
        8036,
        8038,
        8050,
        8051,
        8052,
        8053,
        8057,
        8062,
        8070,
        8077,
        8079,
        8082,
        8084,
        8088,
    }
    for site in LOCAL_STATIC_SITES:
        path = PurePosixPath(site.source_dir)
        assert not path.is_absolute()
        assert path.parts[:3] == ("third_party", "cua-gym-hub", "websites")
        assert path.name.endswith("_mock")


def test_local_static_contract_contains_only_physical_hosting_fields() -> None:
    assert set(LOCAL_STATIC_SITES[0].__dataclass_fields__) == {
        "key",
        "source_dir",
        "port",
    }
