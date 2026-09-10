import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from ili_pipeline.sources.steam import SteamUpstreamError
from ili_pipeline.upcoming import discover, load_snapshot


def row(app_id, release="Coming soon"):
    return (
        f'<a class="search_result_row" data-ds-appid="{app_id}" '
        'data-ds-tagids="[9]"><span class="title">Test &amp; game</span>'
        f'<div class="search_released">{release}</div></a>'
    )


class SearchClient:
    def __init__(self, repeated=False):
        self.repeated = repeated
        self.starts = []

    async def _get_json(self, url, params):
        if "ajaxgetstoretags" in url:
            return {"tags": [{"tagid": 9, "name": "Strategy"}]}
        if params["filter"] == "popularwishlist":
            return {"results_html": row(1)}
        self.starts.append(params["start"])
        app_id = 1 if self.repeated else params["start"] + 1
        release = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()
        return {
            "total_count": 101,
            "results_html": row(app_id, release if app_id == 1 else "Q4 2026"),
        }


def test_discovery_paginates_deduplicates_and_preserves_uncertainty():
    client = SearchClient()
    dataset = asyncio.run(discover(client, delay=0))
    assert client.starts == [0, 100]
    assert dataset.coverage.discovery_complete
    assert dataset.games[0].name == "Test & game"
    assert dataset.games[0].genres == ["Strategy"]
    assert dataset.games[0].attention_weight == 3
    assert dataset.games[1].release_date is None
    assert dataset.games[1].release_date_raw == "Q4 2026"


def test_capped_or_repeated_scan_is_not_complete():
    with pytest.raises(SteamUpstreamError):
        asyncio.run(discover(SearchClient(), max_pages=1, delay=0))
    with pytest.raises(SteamUpstreamError):
        asyncio.run(discover(SearchClient(repeated=True), delay=0))


def test_snapshot_roundtrip_and_corruption(tmp_path):
    path = tmp_path / "upcoming.json"
    assert load_snapshot(path) is None
    dataset = asyncio.run(discover(SearchClient(), delay=0))
    path.write_text(dataset.model_dump_json())
    assert load_snapshot(path) == dataset
    path.write_text("broken JSON")
    assert load_snapshot(path) is None


def test_failed_refresh_preserves_previous_snapshot(tmp_path, monkeypatch):
    from ili_pipeline import upcoming

    path = tmp_path / "upcoming.json"
    path.write_text("previous snapshot")

    async def failed(*args, **kwargs):
        raise SteamUpstreamError("rate limited")

    monkeypatch.setattr(upcoming, "discover", failed)
    with pytest.raises(SteamUpstreamError):
        asyncio.run(upcoming.refresh(path))
    assert path.read_text() == "previous snapshot"


def test_concurrent_refresh_is_rejected_without_network(tmp_path):
    import sqlite3

    from ili_pipeline.upcoming import refresh

    path = tmp_path / "upcoming.json"
    db = sqlite3.connect(path.with_suffix(".lock.sqlite"))
    try:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(SteamUpstreamError, match="already running"):
            asyncio.run(refresh(path))
    finally:
        db.close()


def test_interrupted_discovery_resumes_without_exposing_partial_market(tmp_path):
    checkpoint = tmp_path / "partial.json"
    first = SearchClient()
    with pytest.raises(SteamUpstreamError):
        asyncio.run(discover(first, max_pages=1, delay=0, checkpoint=checkpoint))
    assert first.starts == [0]
    resumed = SearchClient()
    result = asyncio.run(discover(resumed, delay=0, checkpoint=checkpoint))
    assert resumed.starts == [100]
    assert len(result.games) == 2
    assert result.coverage.discovery_complete


def test_unnamed_steam_listing_preserves_app_identity():
    from ili_pipeline.upcoming import SearchRows

    parser = SearchRows()
    parser.feed('<a class="search_result_row" data-ds-appid="42"><span class="title"></span></a>')
    assert parser.rows[0]["app_id"] == 42
    assert parser.rows[0]["name"] == "Steam app 42 (title unavailable)"
