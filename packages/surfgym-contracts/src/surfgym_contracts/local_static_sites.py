"""Physical contracts for local static sites served by the SurfGym fixture host.

This module deliberately owns only deployment identity: a stable key, a
repository-relative source directory, and a fixed loopback port. Task,
evaluation, browser-state, and Docker topology remain outside this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalStaticSite:
    key: str
    source_dir: str
    port: int


LOCAL_STATIC_SITES: tuple[LocalStaticSite, ...] = (
    LocalStaticSite("GITHUB", "third_party/cua-gym-hub/websites/github_mock", 8036),
    LocalStaticSite("GMAIL", "third_party/cua-gym-hub/websites/gmail_mock", 8038),
    LocalStaticSite("HUBSPOT", "third_party/cua-gym-hub/websites/hubspot_mock", 8050),
    LocalStaticSite("INSTACART", "third_party/cua-gym-hub/websites/instacart_mock", 8051),
    LocalStaticSite("INSTAGRAM", "third_party/cua-gym-hub/websites/instagram_mock", 8052),
    LocalStaticSite("JIRA", "third_party/cua-gym-hub/websites/jira_mock", 8053),
    LocalStaticSite("LINKEDIN", "third_party/cua-gym-hub/websites/linkedin_mock", 8057),
    LocalStaticSite(
        "MICROSOFT_TEAMS",
        "third_party/cua-gym-hub/websites/microsoft_teams_mock",
        8062,
    ),
    LocalStaticSite("PINTEREST", "third_party/cua-gym-hub/websites/pinterest_mock", 8070),
    LocalStaticSite(
        "SHOPIFY_ADMIN",
        "third_party/cua-gym-hub/websites/shopify_admin_mock",
        8077,
    ),
    LocalStaticSite(
        "STRIPE_DASHBOARD",
        "third_party/cua-gym-hub/websites/stripe_dashboard_mock",
        8079,
    ),
    LocalStaticSite("TRELLO", "third_party/cua-gym-hub/websites/trello_mock", 8082),
    LocalStaticSite("TWITTER", "third_party/cua-gym-hub/websites/twitter_mock", 8084),
    LocalStaticSite("WECHAT", "third_party/cua-gym-hub/websites/wechat_mock", 8088),
)

LOCAL_STATIC_SITES_BY_KEY = {site.key: site for site in LOCAL_STATIC_SITES}


def get_local_static_site(key: str) -> LocalStaticSite:
    try:
        return LOCAL_STATIC_SITES_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported local static site: {key!r}") from exc
