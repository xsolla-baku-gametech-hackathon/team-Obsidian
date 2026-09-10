from datetime import UTC, date, datetime, timedelta

import pytest
from ili_core.domain.launch import Competitor, Coverage, GameProfile, LaunchRequest, MarketDataset
from ili_core.recommendation.launch import recommend, similarity
from pydantic import ValidationError

NOW = datetime(2026, 9, 10, tzinfo=UTC)


def competitor(app_id=1, **changes):
    values = dict(
        app_id=app_id,
        name=f"Synthetic test game {app_id}",
        genres=["Strategy"],
        tags=["Turn-Based"],
        description="",
        source="synthetic-test-fixture",
        observed_at=NOW,
        release_date=date(2026, 9, 14),
        date_precision="day",
        coming_soon=True,
    )
    return Competitor(**(values | changes))


def request(games=None, **changes):
    dataset = MarketDataset(
        dataset_id="synthetic-test-only",
        collected_at=NOW,
        coverage=Coverage(
            horizon_start=date(2026, 9, 10),
            horizon_end=date(2026, 10, 11),
            discovery_complete=True,
            discovery_method="synthetic exhaustive fixture",
            notes="Synthetic data for tests only, never a live market report.",
        ),
        games=games if games is not None else [competitor()],
    )
    return LaunchRequest(
        **(
            dict(
                game=GameProfile(name="Test target", genres=["Strategy"], tags=["Turn-Based"]),
                dataset=dataset,
                earliest_date=date(2026, 9, 10),
                latest_date=date(2026, 10, 10),
            )
            | changes
        )
    )


def test_rank_and_nonoverlapping_alternatives():
    result = recommend(request(), now=NOW)
    assert result.release.status == "ranked"
    assert result.release.best_date == date(2026, 9, 15)
    assert len(result.release.windows) == 3
    assert all(window.rank == 1 for window in result.release.windows)
    assert all(window.competition_score == 0 for window in result.release.windows)
    intervals = sorted((w.start_date, w.end_date) for w in result.release.windows)
    assert all(left[1] < right[0] for left, right in zip(intervals, intervals[1:]))


@pytest.mark.parametrize(
    "condition",
    [
        "empty",
        "partial",
        "stale",
        "undated",
        "outside",
        "future",
        "old_observation",
        "past_horizon",
    ],
)
def test_abstention(condition):
    payload = request().model_dump(mode="json")
    if condition == "empty":
        payload["dataset"]["games"] = []
    elif condition == "partial":
        payload["dataset"]["coverage"]["discovery_complete"] = False
    elif condition == "stale":
        payload["dataset"]["collected_at"] = "2026-08-01T00:00:00Z"
        payload["dataset"]["games"][0]["observed_at"] = "2026-08-01T00:00:00Z"
    elif condition == "undated":
        payload["dataset"]["games"][0].update(release_date=None, date_precision="quarter")
    elif condition == "outside":
        payload["dataset"]["coverage"]["horizon_end"] = "2026-09-20"
    elif condition == "future":
        payload["dataset"]["collected_at"] = "2026-09-11T00:00:00Z"
        payload["dataset"]["games"][0]["observed_at"] = "2026-09-11T00:00:00Z"
    elif condition == "old_observation":
        payload["dataset"]["games"][0]["observed_at"] = "2026-08-01T00:00:00Z"
    else:
        payload["earliest_date"] = "2026-09-09"
    result = recommend(LaunchRequest.model_validate(payload), now=NOW)
    assert result.release.status == "insufficient_evidence"
    assert result.release.best_date is None
    assert result.release.windows == []


def test_popularity_only_when_comparable_for_every_competitor():
    games = [competitor(1, followers=100000), competitor(2, release_date=date(2026, 9, 21))]
    assert recommend(request(games), now=NOW).release.score_method == "release_count"
    games[1].followers = 10
    result = recommend(request(games, latest_date=date(2026, 9, 23)), now=NOW)
    assert result.release.score_method == "similarity_and_followers"
    # The smaller competitor's week beats the more popular competitor's week.
    assert result.release.best_date == date(2026, 9, 15)


def price_games():
    return [
        competitor(i, coming_soon=False, release_date=date(2026, 1, 1), regular_price_minor=price)
        for i, price in enumerate([999, 1499, 1999, 2499, 2999], 10)
    ]


def test_price_uses_regular_comparable_prices_and_robust_quantiles():
    games = price_games() + [
        competitor(
            20,
            coming_soon=False,
            regular_price_minor=99999,
            release_date=date(2026, 1, 1),
            region="GB",
            currency="GBP",
        )
    ]
    result = recommend(request(games), now=NOW)
    assert result.price.status == "recommended"
    assert result.price.suggested_price_minor == 1999
    assert (result.price.lower_price_minor, result.price.upper_price_minor) == (1499, 2499)
    assert 20 not in result.price.evidence_app_ids
    assert result.release.status == "insufficient_evidence"


@pytest.mark.parametrize(
    "change",
    [
        dict(regular_price_minor=None),
        dict(business_model="free"),
        dict(release_date=date(2020, 1, 1)),
        dict(coming_soon=True),
        dict(observed_at=NOW - timedelta(days=8)),
    ],
)
def test_price_excludes_unusable_comparables(change):
    games = price_games()
    games[0] = Competitor.model_validate(games[0].model_dump() | change)
    assert recommend(request(games), now=NOW).price.status == "insufficient_evidence"


def test_self_exclusion_and_stable_input_order():
    payload = request(price_games() + [competitor()])
    original = recommend(payload, now=NOW)
    payload.dataset.games.reverse()
    assert recommend(payload, now=NOW) == original
    payload.game.app_id = 1
    assert recommend(payload, now=NOW).release.status == "insufficient_evidence"


def test_free_game_and_feature_matching():
    payload = request()
    payload.game.business_model = "free"
    assert recommend(payload, now=NOW).price.suggested_price_minor == 0
    assert similarity(GameProfile(name="Empty"), competitor()) == 0
    assert similarity(payload.game, competitor()) == 1
    assert similarity(payload.game, competitor(genres=["Racing"], tags=["Driving"])) == 0


def test_invalid_input_is_rejected():
    with pytest.raises(ValidationError):
        request([competitor(), competitor()])
    with pytest.raises(ValidationError):
        competitor(date_precision="quarter")
    with pytest.raises(ValidationError):
        request(latest_date=date(2026, 9, 11))
    with pytest.raises(ValidationError):
        competitor(observed_at=datetime(2026, 9, 10))
