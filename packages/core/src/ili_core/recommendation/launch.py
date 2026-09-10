"""Pure, deterministic recommendations. No network calls or learned success claims."""

import math
import re
from datetime import UTC, datetime, timedelta

from ili_core.domain.launch import (
    Competitor,
    GameProfile,
    LaunchReport,
    LaunchRequest,
    MatchedCompetitor,
    PriceAdvice,
    ReleaseAdvice,
    ReleaseWindow,
)

MIN_SIMILARITY = 0.15
MAX_AGE_DAYS = 7
PRICE_HISTORY_DAYS = 730
STOP_WORDS = {"the", "and", "with", "your", "you", "for", "this", "that", "game", "play"}


def labels(values: list[str]) -> set[str]:
    return {value.strip().casefold() for value in values if value.strip()}


def overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def similarity(target: GameProfile, other: GameProfile) -> float:
    """Weighted Jaccard; missing target features do not dilute available features."""

    def tokens(text: str) -> set[str]:
        return set(re.findall(r"\w{3,}", text.casefold())) - STOP_WORDS

    features = [
        (0.45, labels(target.tags), labels(other.tags)),
        (0.35, labels(target.genres), labels(other.genres)),
        (0.20, tokens(target.description), tokens(other.description)),
    ]
    denominator = sum(weight for weight, left, _ in features if left)
    if not denominator:
        return 0.0
    score = sum(weight * overlap(left, right) for weight, left, right in features)
    return score / denominator


def _price(
    request: LaunchRequest, matches: list[tuple[Competitor, float]], now: datetime
) -> PriceAdvice:
    common = {"currency": request.currency, "region": request.region}
    if request.game.business_model == "free":
        return PriceAdvice(
            **common,
            status="free_to_play",
            suggested_price_minor=0,
            lower_price_minor=0,
            upper_price_minor=0,
            explanation="Free-to-play selected. "
            "This model does not recommend in-game monetization.",
        )
    comparables = [
        (game, weight)
        for game, weight in matches
        if not game.coming_soon
        and game.business_model == "premium"
        and game.regular_price_minor is not None
        and game.regular_price_minor > 0
        and game.currency == request.currency
        and game.region == request.region
        and game.release_date is not None
        and 0 <= (now.date() - game.release_date).days <= PRICE_HISTORY_DAYS
        and (now - game.observed_at).total_seconds() <= MAX_AGE_DAYS * 86400
        and (
            request.game.playtime_hours is None
            or game.playtime_hours is None
            or 0.5 <= game.playtime_hours / request.game.playtime_hours <= 2
        )
    ]
    if len(comparables) < 5:
        return PriceAdvice(
            **common,
            status="insufficient_evidence",
            explanation="Need at least five fresh, similar, paid games released in the last "
            "two years with regular prices in the requested region and currency.",
            evidence_app_ids=[game.app_id for game, _ in comparables],
        )
    comparables.sort(key=lambda pair: (pair[0].regular_price_minor, pair[0].app_id))

    def quantile(fraction: float) -> int:
        threshold = fraction * sum(weight for _, weight in comparables)
        cumulative = 0.0
        for game, weight in comparables:
            cumulative += weight
            if cumulative >= threshold:
                return int(game.regular_price_minor)
        return int(comparables[-1][0].regular_price_minor)

    return PriceAdvice(
        **common,
        status="recommended",
        suggested_price_minor=quantile(0.5),
        lower_price_minor=quantile(0.25),
        upper_price_minor=quantile(0.75),
        evidence_app_ids=[game.app_id for game, _ in comparables],
        explanation="Similarity-weighted median and middle 50% of comparable regular prices. "
        "This is market positioning, not an estimate of the revenue-maximizing price.",
    )


def recommend(request: LaunchRequest, *, now: datetime | None = None) -> LaunchReport:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    dataset = request.dataset
    warnings = []
    usable = [game for game in dataset.games if game.observed_at <= now]
    if len(usable) != len(dataset.games):
        warnings.append("Future observations were excluded.")
    matches = [
        (game, similarity(request.game, game))
        for game in usable
        if game.app_id != request.game.app_id
    ]
    matches = [(game, score) for game, score in matches if score >= MIN_SIMILARITY]
    matches.sort(key=lambda pair: (-pair[1], pair[0].app_id))
    upcoming = [(game, score) for game, score in matches if game.coming_soon]
    undated = sum(game.release_date is None for game, _ in upcoming)
    coverage = dataset.coverage
    blockers = []
    if not coverage.discovery_complete:
        blockers.append(
            "Upcoming-release discovery is incomplete; a curated sample cannot "
            "establish quiet weeks."
        )
    if (
        coverage.horizon_start > request.earliest_date
        or coverage.horizon_end <= request.latest_date
    ):
        blockers.append("The dataset does not cover the requested release horizon.")
    if not 0 <= (now - dataset.collected_at).total_seconds() <= MAX_AGE_DAYS * 86400:
        blockers.append("The dataset is future-dated or older than seven days.")
    if request.earliest_date < now.date():
        blockers.append("Release recommendations require a present or future horizon.")
    if any((now - game.observed_at).total_seconds() > MAX_AGE_DAYS * 86400 for game, _ in upcoming):
        blockers.append("Upcoming competitor observations are older than seven days.")
    if len(usable) != len(dataset.games):
        blockers.append("The dataset contains future observations.")
    if undated:
        blockers.append("Similar upcoming games have unknown or approximate release dates.")
    dated = [
        (game, score)
        for game, score in upcoming
        if game.release_date is not None
        and request.earliest_date <= game.release_date <= request.latest_date
    ]
    if not dated:
        blockers.append(
            "No dated competitors were observed in the requested horizon; "
            "this is insufficient evidence for a best week."
        )
    # Strength is enabled only when the same signal is present for every dated competitor.
    use_strength = bool(dated) and all(game.followers is not None for game, _ in dated)
    method = "similarity_and_followers" if use_strength else "release_count"
    if not use_strength:
        warnings.append(
            "Comparable follower counts are unavailable; release ranking uses "
            "observed competitor counts, without treating missing popularity as zero."
        )
    windows = []
    if not blockers:
        max_log = max(math.log1p(game.followers) for game, _ in dated) if use_strength else 0
        start = request.earliest_date
        while start + timedelta(days=6) <= request.latest_date:
            end = start + timedelta(days=6)
            evidence = [(game, score) for game, score in dated if start <= game.release_date <= end]
            score = float(len(evidence))
            if use_strength:
                score = sum(
                    sim * (1 + (math.log1p(game.followers) / max_log if max_log else 0))
                    for game, sim in evidence
                )
            windows.append(
                ReleaseWindow(
                    start_date=start,
                    end_date=end,
                    rank=0,
                    competition_score=round(score, 6),
                    observed_release_count=len(evidence),
                    evidence_app_ids=sorted(game.app_id for game, _ in evidence),
                    explanation=f"{len(evidence)} similar announced releases "
                    "in this seven-day window. "
                    "Lower scores indicate less observed competition, not higher predicted sales.",
                )
            )
            start += timedelta(days=1)
        windows.sort(key=lambda row: (row.competition_score, row.start_date))
        previous = None
        rank = 0
        for index, window in enumerate(windows, 1):
            if window.competition_score != previous:
                rank = index
            window.rank = rank
            previous = window.competition_score
        # Return distinct alternatives, retaining ties from the full ranking.
        selected = []
        for window in windows:
            if all(
                window.end_date < other.start_date or window.start_date > other.end_date
                for other in selected
            ):
                selected.append(window)
                if len(selected) == 3:
                    break
        windows = selected
    release = ReleaseAdvice(
        status="insufficient_evidence" if blockers else "ranked",
        best_date=windows[0].start_date if windows else None,
        windows=windows,
        score_method=method,
        undated_competitor_count=undated,
        explanation=" ".join(blockers)
        if blockers
        else "Recommended date is the start of the lowest-scoring seven-day window. "
        "Equal scores share a rank; earlier starts break ties. "
        "There is no learned daily sales effect.",
    )
    price = _price(request, matches, now)
    recommendations = [
        "Recheck announced competitor dates before committing; release schedules can change.",
        "Check Steam event dates and your production readiness before choosing a launch window.",
    ]
    if price.status == "recommended":
        recommendations.append(
            "Validate the suggested price against your game's content and "
            "audience willingness to pay before setting it in Steamworks."
        )
    if not request.game.tags:
        recommendations.append("Add gameplay and audience tags to improve competitor matching.")
    warnings.extend(
        [
            "Recommendations describe the supplied dataset; discovery completeness is declared by "
            "its producer and cannot be verified by the model.",
            "Event calendars, marketing budgets, wishlists, and sales outcomes are not modeled.",
            "Confidence is a data-quality label, not a calibrated probability of success.",
        ]
    )
    return LaunchReport(
        dataset_id=dataset.dataset_id,
        generated_at=now,
        confidence="medium" if not blockers and price.status == "recommended" else "low",
        competitors=[
            MatchedCompetitor(
                app_id=game.app_id,
                name=game.name,
                similarity=round(score, 4),
                shared_genres=sorted(labels(request.game.genres) & labels(game.genres)),
                shared_tags=sorted(labels(request.game.tags) & labels(game.tags)),
                release_date=game.release_date,
                followers=game.followers,
            )
            for game, score in matches[:20]
        ],
        release=release,
        price=price,
        recommendations=recommendations,
        warnings=warnings,
    )
