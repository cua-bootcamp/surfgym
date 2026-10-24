from urllib.parse import parse_qsl, urlsplit

from surfgym_contracts.task import Website
from surfgym_runtime.wavepool.instance.service import _native_entry_url


def test_native_entry_url_has_no_internal_lifecycle_descriptor() -> None:
    website = Website(website_id="_", url="http://127.0.0.1:53001/vscode")

    serialized = _native_entry_url(website)
    query = dict(parse_qsl(urlsplit(serialized).query, keep_blank_values=True))

    assert website.surface == "native"
    assert query == {}
