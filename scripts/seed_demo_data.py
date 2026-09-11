from __future__ import annotations

# ruff: noqa: E402,I001

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
VENV_PYTHON = (
    REPO_DIR / ".venv" / "Scripts" / "python.exe"
    if sys.platform.startswith("win")
    else REPO_DIR / ".venv" / "bin" / "python"
)

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    import os

    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

sys.path[:0] = [
    str(REPO_DIR / "packages/core/src"),
    str(REPO_DIR / "apps/api/src"),
    str(REPO_DIR / "pipelines/src"),
]

from ili_core.storage.users import AuthConflict, UserStore


DEFAULT_OUTPUT = REPO_DIR / "data" / "processed" / "demo-users.sqlite"
DEMO_PASSWORD = "Demo-password1"


def report_payload(app_id: int, name: str) -> dict:
    return {
        "game": {"app_id": app_id, "name": name},
        "target_source": "demo_seed",
        "competitors": [],
        "report": {
            "price": {"suggested_price_minor": 1999, "currency": "USD"},
            "release": {"status": "ranked"},
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }


def create_user(store: UserStore, *, email: str, name: str):
    try:
        return store.create_user(email=email, password=DEMO_PASSWORD, display_name=name)
    except AuthConflict:
        return store.authenticate(email=email, password=DEMO_PASSWORD)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a demo user/marketplace SQLite database.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reset", action="store_true", help="Delete the output database first.")
    args = parser.parse_args()

    output = args.output.resolve()
    if args.reset and output.exists():
        output.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{output}{suffix}")
            if sidecar.exists():
                sidecar.unlink()

    store = UserStore(output)
    store.initialize()

    developer = create_user(store, email="gamedev@demo.studio", name="Demo Game Developer")
    creator = create_user(store, email="creator@demo.channel", name="Demo Content Creator")

    developer = store.select_subscription(user_id=developer.id, plan="pro", role="game_developer")
    creator = store.select_subscription(user_id=creator.id, plan="starter", role="content_creator")
    creator = store.verify_youtube(
        user_id=creator.id,
        channel_id="UC-demo-launchpad",
        google_subject="demo-google-subject",
    )

    marketplace_games = [
        {
            "app_id": 3669870,
            "name": "CONTROL Resonant",
            "pitch": (
                "Coming 24 Sep 2026. Paranatural action RPG from Remedy with cinematic combat, "
                "story-rich worldbuilding, and strong preview value for creators."
            ),
            "message": (
                "My channel covers action RPGs and cinematic story games; I would like to "
                "prepare a launch-week impressions video."
            ),
        },
        {
            "app_id": 1636440,
            "name": "SILENT HILL: Townfall",
            "pitch": (
                "Coming 23 Sep 2026. Psychological horror with high creator appeal for lore "
                "breakdowns, first reactions, and atmospheric gameplay coverage."
            ),
            "message": "I make horror essays and first-look videos focused on atmosphere and story.",
        },
        {
            "app_id": 4115450,
            "name": "Phantom Blade Zero",
            "pitch": (
                "Coming 28 Oct 2026. Wuxia action RPG with fast combat, boss fights, and "
                "high-skill gameplay moments built for creator showcases."
            ),
            "message": (
                "I cover souls-like and action games, and this would fit a combat preview series."
            ),
        },
        {
            "app_id": 3259780,
            "name": "FINAL FANTASY RESONANCE",
            "pitch": (
                "Coming 22 Oct 2026. Pixel-art JRPG revival with party combat, companion drama, "
                "and strong nostalgia hooks for RPG creators."
            ),
            "message": "My audience follows JRPG releases and retro-inspired RPG coverage.",
        },
        {
            "app_id": 4358690,
            "name": "Graveyard Keeper 2",
            "pitch": (
                "Coming 22 Sep 2026. Dark comedy management sim with automation, cemetery "
                "building, and quirky systems for cozy-sim and strategy creators."
            ),
            "message": None,
        },
        {
            "app_id": 4080220,
            "name": "EA SPORTS FC™ 27",
            "pitch": (
                "Coming 24 Sep 2026. Major sports release with football creator demand, "
                "mode coverage, and launch comparison content potential."
            ),
            "message": None,
        },
        {
            "app_id": 3393110,
            "name": "AION 2",
            "pitch": (
                "Coming 5 Oct 2026. Free-to-play MMORPG launch with creator opportunities "
                "around classes, world exploration, and early progression guides."
            ),
            "message": "I cover MMO launches and would like to prepare a beginner guide.",
        },
        {
            "app_id": 4705510,
            "name": "Happy Wheels",
            "pitch": (
                "Coming 21 Sep 2026. Physics sandbox chaos with instant short-form appeal, "
                "challenge runs, and funny creator moments."
            ),
            "message": "This is perfect for short-form comedy gameplay clips on my channel.",
        },
        {
            "app_id": 4824610,
            "name": "Resident Evil Veronica",
            "pitch": (
                "Planned for 2027. Survival horror remake with major franchise attention, "
                "reaction content, lore videos, and launch-week review potential."
            ),
            "message": None,
        },
        {
            "app_id": 3216600,
            "name": "KINGDOM HEARTS IV",
            "pitch": (
                "Expected 2027. Major action RPG sequel with strong fan demand, reaction "
                "videos, lore explainers, and character-focused creator coverage."
            ),
            "message": "I create RPG lore videos and would like early access for story coverage.",
        },
        {
            "app_id": 2719590,
            "name": "Light No Fire",
            "pitch": (
                "Release date to be announced. Large-scale survival exploration from Hello "
                "Games with huge wishlist interest and discovery-focused creator potential."
            ),
            "message": "My channel focuses on open-world survival and exploration games.",
        },
    ]

    reports = [
        store.save_report(
            user_id=developer.id,
            steam_url=f"https://store.steampowered.com/app/{game['app_id']}/",
            report_payload=report_payload(game["app_id"], game["name"]),
        )
        for game in marketplace_games
    ]

    published_games = []
    for report, game in zip(reports, marketplace_games, strict=True):
        application = store.create_ownership_application(
            user_id=developer.id,
            report_id=report.id,
            studio_name="Demo Studio",
            applicant_name="Demo Game Developer",
            applicant_title="Publishing Manager",
            business_email="publishing@demo.studio",
            company_website_url="https://demo.studio",
            official_contact_url=f"https://demo.studio/press/{game['app_id']}",
            steamworks_proof_url=f"https://demo.studio/private/steamworks-{game['app_id']}",
            proof_url=f"https://demo.studio/games/{game['app_id']}",
            proof_notes=(
                "Business email domain matches the studio website. The press page, game page, "
                "and private Steamworks proof all reference the same Steam app."
            ),
        )
        store.set_ownership_status(
            application_id=application.id,
            status="approved",
            reviewed_notes="Approved for demo. Studio identity and proof links match.",
        )
        published_games.append(
            store.publish_game(
                user_id=developer.id,
                ownership_application_id=application.id,
                pitch=game["pitch"],
                contact_email="keys@demo.studio",
            )
        )

    pending_report = store.save_report(
        user_id=developer.id,
        steam_url="https://store.steampowered.com/app/413150/",
        report_payload=report_payload(413150, "Stardew Valley"),
    )
    store.create_ownership_application(
        user_id=developer.id,
        report_id=pending_report.id,
        studio_name="Demo Studio",
        applicant_name="Demo Game Developer",
        applicant_title="Founder",
        business_email="publishing@demo.studio",
        company_website_url="https://demo.studio",
        official_contact_url=None,
        steamworks_proof_url="https://demo.studio/private/stardew-proof",
        proof_url=None,
        proof_notes="Pending demo application with enough proof for platform owner review.",
    )

    rejected_report = store.save_report(
        user_id=developer.id,
        steam_url="https://store.steampowered.com/app/105600/",
        report_payload=report_payload(105600, "Terraria"),
    )
    rejected = store.create_ownership_application(
        user_id=developer.id,
        report_id=rejected_report.id,
        studio_name="Wrong Studio",
        applicant_name="Demo Game Developer",
        applicant_title="Producer",
        business_email="producer@demo.studio",
        company_website_url="https://demo.studio",
        official_contact_url=None,
        steamworks_proof_url=None,
        proof_url="https://demo.studio/unrelated-game",
        proof_notes=(
            "Rejected demo application where the public proof does not match the Steam app."
        ),
    )
    store.set_ownership_status(
        application_id=rejected.id,
        status="rejected",
        reviewed_notes="Rejected for demo. Evidence does not prove ownership of this Steam app.",
    )

    for game, published in zip(marketplace_games, published_games, strict=True):
        if not game["message"]:
            continue
        store.create_key_request(
            creator_user_id=creator.id,
            game_id=published.id,
            message=game["message"],
        )

    with sqlite3.connect(output) as db:
        ownership_count = db.execute("SELECT COUNT(*) FROM ownership_applications").fetchone()[0]
        game_count = db.execute("SELECT COUNT(*) FROM published_games").fetchone()[0]
        request_count = db.execute("SELECT COUNT(*) FROM key_requests").fetchone()[0]

    print(f"Created demo database: {output}")
    print(f"Developer login: gamedev@demo.studio / {DEMO_PASSWORD}")
    print(f"Creator login:   creator@demo.channel / {DEMO_PASSWORD}")
    print(f"Ownership applications: {ownership_count}")
    print(f"Published games: {game_count}")
    print(f"Key requests: {request_count}")
    print("Run with this database:")
    print(f"ILI_USER_DB_PATH={output} python scripts/dev.py")


if __name__ == "__main__":
    main()
