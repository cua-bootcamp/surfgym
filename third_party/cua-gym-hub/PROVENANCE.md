# CUA-Gym-Hub provenance

The application sources in this directory are vendored from
[xlang-ai/CUA-Gym-Hub](https://github.com/xlang-ai/CUA-Gym-Hub) at revision
`53205689c3d88078c1375f76466d5bd799478828`.

The vendored upstream project is licensed under Apache-2.0. A copy of its
license is preserved in `LICENSE`.

The existing `instacart_mock` pilot and these reviewed direct-web applications
are retained under `websites/`:

- `github_mock`
- `gmail_mock`
- `hubspot_mock`
- `instagram_mock`
- `jira_mock`
- `linkedin_mock`
- `microsoft_teams_mock`
- `pinterest_mock`
- `shopify_admin_mock`
- `stripe_dashboard_mock`
- `trello_mock`
- `twitter_mock`
- `wechat_mock`

SurfGym-specific differences are limited to the app-owned SID-scoped state
helpers, the first-import `window.surfgym` bridge, package test wiring, and
focused bridge tests. The offline onboarding audit in
`surfgym_task.cua.onboarding` verifies those differences against the pinned
upstream application trees and rejects unallowlisted runtime changes.

`websites/instacart_mock/PATCHES.json` records the pilot's additional functional
and Tailwind build-chain changes. It is app-local audit metadata, not an
application registry or runtime/configuration input. The strict record pins the
upstream revision and the exact eleven exceptional modified files using
cross-platform `sha256-lf-v1` hashes. Its full source commits and task identifiers
are bounded declared lineage metadata for traceability, not existence-validated
Git or task-data references.
Seven preserve functional or build-chain behavior; four retain the existing
whitespace-clean formatting without semantic changes or upstream whitespace debt.
Ordinary bridge, state, entry, package, and focused-test allowances remain owned
by the generic onboarding audit and are not duplicated in this record.

`shared/secureMockApiPlugin.mjs` was already present in SurfGym and matches the
pinned upstream helper, so onboarding preserves the existing copy.
