from __future__ import annotations

# ruff: noqa: E402,I001

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
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

    reports = [
        store.save_report(
            user_id=developer.id,
            steam_url="https://store.steampowered.com/app/3354750/",
            report_payload=report_payload(3354750, "skate."),
        ),
        store.save_report(
            user_id=developer.id,
            steam_url="https://store.steampowered.com/app/1431300/",
            report_payload=report_payload(1431300, "SAND"),
        ),
        store.save_report(
            user_id=developer.id,
            steam_url="https://store.steampowered.com/app/413150/",
            report_payload=report_payload(413150, "Stardew Valley"),
        ),
    ]

    approved = store.create_ownership_application(
        user_id=developer.id,
        report_id=reports[0].id,
        studio_name="Demo Studio",
        applicant_name="Demo Game Developer",
        applicant_title="Founder",
        business_email="publishing@demo.studio",
        company_website_url="https://demo.studio",
        official_contact_url="https://demo.studio/press",
        steamworks_proof_url="https://demo.studio/private/steamworks-proof",
        proof_url="https://demo.studio/skate-press-kit",
        proof_notes=(
            "Business email domain matches the studio website. The press page links to the "
            "same game and the private proof link contains Steamworks ownership evidence."
        ),
    )
    store.set_ownership_status(
        application_id=approved.id,
        status="approved",
        reviewed_notes="Approved for demo. Studio identity and proof links match.",
    )

    store.create_ownership_application(
        user_id=developer.id,
        report_id=reports[1].id,
        studio_name="Demo Studio",
        applicant_name="Demo Game Developer",
        applicant_title="Publishing Manager",
        business_email="publishing@demo.studio",
        company_website_url="https://demo.studio",
        official_contact_url=None,
        steamworks_proof_url="https://demo.studio/private/sand-proof",
        proof_url=None,
        proof_notes="Pending demo application with enough proof for platform owner review.",
    )

    rejected = store.create_ownership_application(
        user_id=developer.id,
        report_id=reports[2].id,
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

    published = store.publish_game(
        user_id=developer.id,
        ownership_application_id=approved.id,
        pitch=(
            "Open-world skateboarding with online play, expressive traversal, and strong creator "
            "clip potential for launch-week coverage."
        ),
        contact_email="keys@demo.studio",
    )
    store.create_key_request(
        creator_user_id=creator.id,
        game_id=published.id,
        message=(
            "I create PC indie coverage videos and would like to prepare a preview for my "
            "upcoming Steam releases series."
        ),
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
