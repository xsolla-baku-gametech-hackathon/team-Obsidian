"""SQLite-backed user and session store."""

import hashlib
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from ili_core.domain.auth import (
    AuthSession,
    SubscriptionPlan,
    SubscriptionStatus,
    UserAccount,
    UserRole,
)
from ili_core.domain.marketplace import (
    KeyRequest,
    OwnershipApplication,
    OwnershipStatus,
    PublishedGame,
)
from ili_core.domain.reports import ReportSummary, SavedReport


class AuthConflict(Exception):
    pass


class AuthInvalidCredentials(Exception):
    pass


class AuthUnauthorized(Exception):
    pass


class AuthForbidden(Exception):
    pass


class ReportNotFound(Exception):
    pass


class MarketplaceNotFound(Exception):
    pass


class UserStore:
    def __init__(self, path: Path, session_ttl: timedelta = timedelta(days=7)) -> None:
        self.path = path.resolve()
        self.session_ttl = session_ttl
        self._hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    password_hash TEXT NOT NULL,
                    premium_role TEXT CHECK (
                        premium_role IN ('game_developer', 'content_creator')
                        OR premium_role IS NULL
                    ),
                    subscription_plan TEXT CHECK (
                        subscription_plan IN ('starter', 'pro', 'studio')
                        OR subscription_plan IS NULL
                    ),
                    subscription_status TEXT NOT NULL DEFAULT 'inactive'
                        CHECK (
                            subscription_status IN (
                                'inactive', 'active', 'pending_youtube_verification'
                            )
                        ),
                    youtube_channel_id TEXT,
                    youtube_google_subject TEXT,
                    youtube_verified_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS sessions_expires_at ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS user_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    steam_url TEXT NOT NULL,
                    app_id INTEGER NOT NULL,
                    game_name TEXT NOT NULL,
                    target_source TEXT NOT NULL,
                    suggested_price_minor INTEGER,
                    price_currency TEXT,
                    release_status TEXT NOT NULL,
                    competitor_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS user_reports_user_created
                    ON user_reports(user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS ownership_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    report_id INTEGER NOT NULL REFERENCES user_reports(id) ON DELETE CASCADE,
                    app_id INTEGER NOT NULL,
                    game_name TEXT NOT NULL,
                    steam_url TEXT NOT NULL,
                    studio_name TEXT NOT NULL,
                    applicant_name TEXT NOT NULL DEFAULT '',
                    applicant_title TEXT NOT NULL DEFAULT '',
                    business_email TEXT NOT NULL DEFAULT '',
                    company_website_url TEXT,
                    official_contact_url TEXT,
                    steamworks_proof_url TEXT,
                    proof_url TEXT,
                    proof_notes TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
                    reviewed_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, app_id)
                );
                CREATE INDEX IF NOT EXISTS ownership_applications_user_created
                    ON ownership_applications(user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS published_games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    ownership_application_id INTEGER NOT NULL UNIQUE
                        REFERENCES ownership_applications(id) ON DELETE CASCADE,
                    app_id INTEGER NOT NULL UNIQUE,
                    game_name TEXT NOT NULL,
                    steam_url TEXT NOT NULL,
                    pitch TEXT NOT NULL,
                    contact_email TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS published_games_created
                    ON published_games(created_at DESC);
                CREATE TABLE IF NOT EXISTS key_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL REFERENCES published_games(id) ON DELETE CASCADE,
                    creator_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(game_id, creator_user_id)
                );
                CREATE INDEX IF NOT EXISTS key_requests_creator_created
                    ON key_requests(creator_user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS key_requests_owner_created
                    ON key_requests(owner_user_id, created_at DESC);
                """
            )
            self._ensure_column(
                db, "ownership_applications", "applicant_name", "TEXT NOT NULL DEFAULT ''"
            )
            self._ensure_column(
                db, "ownership_applications", "applicant_title", "TEXT NOT NULL DEFAULT ''"
            )
            self._ensure_column(
                db, "ownership_applications", "business_email", "TEXT NOT NULL DEFAULT ''"
            )
            self._ensure_column(db, "ownership_applications", "company_website_url", "TEXT")
            self._ensure_column(db, "ownership_applications", "official_contact_url", "TEXT")
            self._ensure_column(db, "ownership_applications", "steamworks_proof_url", "TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_user(self, *, email: str, password: str, display_name: str | None) -> UserAccount:
        now = self._now()
        password_hash = self._hasher.hash(password)
        try:
            with closing(self._connect()) as db:
                cursor = db.execute(
                    """
                    INSERT INTO users (email, display_name, password_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self._email(email), display_name, password_hash, now, now),
                )
                db.commit()
                user_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise AuthConflict("An account with this email already exists.") from exc
        user = self.get_user(user_id)
        if user is None:
            raise RuntimeError("Created user could not be loaded")
        return user

    def authenticate(self, *, email: str, password: str) -> UserAccount:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM users WHERE email = ?",
                (self._email(email),),
            ).fetchone()
            if row is None:
                raise AuthInvalidCredentials("Invalid email or password.")
            try:
                ok = self._hasher.verify(row["password_hash"], password)
            except VerifyMismatchError as exc:
                raise AuthInvalidCredentials("Invalid email or password.") from exc
            if not ok:
                raise AuthInvalidCredentials("Invalid email or password.")
            if self._hasher.check_needs_rehash(row["password_hash"]):
                db.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (self._hasher.hash(password), self._now(), row["id"]),
                )
                db.commit()
            return self._user(row)

    def create_session(self, user: UserAccount) -> AuthSession:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = now + self.session_ttl
        with closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO sessions (token_hash, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (self._token_hash(token), user.id, expires_at.isoformat(), now.isoformat()),
            )
            db.commit()
        return AuthSession(access_token=token, expires_at=expires_at, user=user)

    def get_user_by_token(self, token: str) -> UserAccount:
        self.prune_expired_sessions()
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT users.* FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (self._token_hash(token), self._now()),
            ).fetchone()
        if row is None:
            raise AuthUnauthorized("Authentication is required.")
        return self._user(row)

    def delete_session(self, token: str) -> None:
        with closing(self._connect()) as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (self._token_hash(token),))
            db.commit()

    def prune_expired_sessions(self) -> None:
        with closing(self._connect()) as db:
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (self._now(),))
            db.commit()

    def get_user(self, user_id: int) -> UserAccount | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._user(row) if row else None

    def select_subscription(
        self, *, user_id: int, plan: SubscriptionPlan, role: UserRole
    ) -> UserAccount:
        status: SubscriptionStatus = (
            "pending_youtube_verification" if role == "content_creator" else "active"
        )
        now = self._now()
        with closing(self._connect()) as db:
            db.execute(
                """
                UPDATE users
                SET premium_role = ?, subscription_plan = ?, subscription_status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (role, plan, status, now, user_id),
            )
            db.commit()
        user = self.get_user(user_id)
        if user is None:
            raise AuthUnauthorized("Authentication is required.")
        return user

    def verify_youtube(
        self, *, user_id: int, channel_id: str, google_subject: str
    ) -> UserAccount:
        now = self._now()
        with closing(self._connect()) as db:
            db.execute(
                """
                UPDATE users
                SET youtube_channel_id = ?, youtube_google_subject = ?,
                    youtube_verified_at = ?, subscription_status = 'active', updated_at = ?
                WHERE id = ? AND premium_role = 'content_creator'
                """,
                (channel_id, google_subject, now, now, user_id),
            )
            if db.total_changes == 0:
                raise AuthUnauthorized("Choose the content creator plan before verification.")
            db.commit()
        user = self.get_user(user_id)
        if user is None:
            raise AuthUnauthorized("Authentication is required.")
        return user

    def save_report(
        self, *, user_id: int, steam_url: str, report_payload: dict[str, Any]
    ) -> SavedReport:
        now = self._now()
        game = report_payload["game"]
        report = report_payload["report"]
        price = report["price"]
        release = report["release"]
        competitor_count = len(report_payload.get("competitors", []))
        with closing(self._connect()) as db:
            cursor = db.execute(
                """
                INSERT INTO user_reports (
                    user_id, steam_url, app_id, game_name, target_source,
                    suggested_price_minor, price_currency, release_status,
                    competitor_count, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    steam_url,
                    int(game["app_id"]),
                    str(game["name"]),
                    str(report_payload["target_source"]),
                    price.get("suggested_price_minor"),
                    price.get("currency"),
                    str(release["status"]),
                    competitor_count,
                    json.dumps(report_payload, separators=(",", ":")),
                    now,
                ),
            )
            db.commit()
            report_id = int(cursor.lastrowid)
        return self.get_report(user_id=user_id, report_id=report_id)

    def list_reports(self, *, user_id: int, limit: int = 50) -> list[ReportSummary]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, steam_url, app_id, game_name, target_source,
                    suggested_price_minor, price_currency, release_status,
                    competitor_count, created_at
                FROM user_reports
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._report_summary(row) for row in rows]

    def get_report(self, *, user_id: int, report_id: int) -> SavedReport:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT id, steam_url, app_id, game_name, target_source,
                    suggested_price_minor, price_currency, release_status,
                    competitor_count, payload_json, created_at
                FROM user_reports
                WHERE id = ? AND user_id = ?
                """,
                (report_id, user_id),
            ).fetchone()
        if row is None:
            raise ReportNotFound("Report was not found.")
        summary = self._report_summary(row)
        return SavedReport(**summary.model_dump(), payload=json.loads(row["payload_json"]))

    def create_ownership_application(
        self,
        *,
        user_id: int,
        report_id: int,
        studio_name: str,
        applicant_name: str,
        applicant_title: str,
        business_email: str,
        company_website_url: str | None,
        official_contact_url: str | None,
        steamworks_proof_url: str | None,
        proof_url: str | None,
        proof_notes: str,
    ) -> OwnershipApplication:
        report = self.get_report(user_id=user_id, report_id=report_id)
        now = self._now()
        try:
            with closing(self._connect()) as db:
                cursor = db.execute(
                    """
                    INSERT INTO ownership_applications (
                        user_id, report_id, app_id, game_name, steam_url, studio_name,
                        applicant_name, applicant_title, business_email, company_website_url,
                        official_contact_url, steamworks_proof_url, proof_url, proof_notes,
                        status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        user_id,
                        report_id,
                        report.app_id,
                        report.game_name,
                        report.steam_url,
                        studio_name,
                        applicant_name,
                        applicant_title,
                        business_email,
                        company_website_url,
                        official_contact_url,
                        steamworks_proof_url,
                        proof_url,
                        proof_notes,
                        now,
                        now,
                    ),
                )
                db.commit()
                application_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise AuthConflict("Ownership verification is already open for this game.") from exc
        return self.get_ownership_application(user_id=user_id, application_id=application_id)

    def list_ownership_applications(self, *, user_id: int) -> list[OwnershipApplication]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT * FROM ownership_applications
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._ownership_application(row) for row in rows]

    def list_all_ownership_applications(self) -> list[OwnershipApplication]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT * FROM ownership_applications
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._ownership_application(row) for row in rows]

    def get_ownership_application(
        self, *, user_id: int, application_id: int
    ) -> OwnershipApplication:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM ownership_applications WHERE id = ? AND user_id = ?",
                (application_id, user_id),
            ).fetchone()
        if row is None:
            raise MarketplaceNotFound("Ownership application was not found.")
        return self._ownership_application(row)

    def set_ownership_status(
        self, *, application_id: int, status: OwnershipStatus, reviewed_notes: str | None = None
    ) -> OwnershipApplication:
        now = self._now()
        with closing(self._connect()) as db:
            db.execute(
                """
                UPDATE ownership_applications
                SET status = ?, reviewed_notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, reviewed_notes, now, application_id),
            )
            if db.total_changes == 0:
                raise MarketplaceNotFound("Ownership application was not found.")
            row = db.execute(
                "SELECT * FROM ownership_applications WHERE id = ?", (application_id,)
            ).fetchone()
            db.commit()
        return self._ownership_application(row)

    def publish_game(
        self,
        *,
        user_id: int,
        ownership_application_id: int,
        pitch: str,
        contact_email: str | None,
    ) -> PublishedGame:
        application = self.get_ownership_application(
            user_id=user_id, application_id=ownership_application_id
        )
        if application.status != "approved":
            raise AuthForbidden("Game ownership must be approved before publishing.")
        now = self._now()
        try:
            with closing(self._connect()) as db:
                cursor = db.execute(
                    """
                    INSERT INTO published_games (
                        owner_user_id, ownership_application_id, app_id, game_name,
                        steam_url, pitch, contact_email, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        ownership_application_id,
                        application.app_id,
                        application.game_name,
                        application.steam_url,
                        pitch,
                        contact_email,
                        now,
                        now,
                    ),
                )
                db.commit()
                game_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise AuthConflict("This game has already been published.") from exc
        return self.get_published_game(game_id=game_id)

    def list_published_games(self) -> list[PublishedGame]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM published_games ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._published_game(row) for row in rows]

    def get_published_game(self, *, game_id: int) -> PublishedGame:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM published_games WHERE id = ?", (game_id,)).fetchone()
        if row is None:
            raise MarketplaceNotFound("Published game was not found.")
        return self._published_game(row)

    def create_key_request(
        self, *, creator_user_id: int, game_id: int, message: str
    ) -> KeyRequest:
        game = self.get_published_game(game_id=game_id)
        if game.owner_user_id == creator_user_id:
            raise AuthForbidden("You cannot request a key for your own game.")
        now = self._now()
        try:
            with closing(self._connect()) as db:
                cursor = db.execute(
                    """
                    INSERT INTO key_requests (
                        game_id, creator_user_id, owner_user_id, message, status,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (game_id, creator_user_id, game.owner_user_id, message, now, now),
                )
                db.commit()
                request_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise AuthConflict("You already requested a key for this game.") from exc
        return self._get_key_request(request_id=request_id)

    def list_creator_key_requests(self, *, creator_user_id: int) -> list[KeyRequest]:
        return self._list_key_requests("creator_user_id", creator_user_id)

    def list_owner_key_requests(self, *, owner_user_id: int) -> list[KeyRequest]:
        return self._list_key_requests("owner_user_id", owner_user_id)

    def _list_key_requests(self, column: str, user_id: int) -> list[KeyRequest]:
        with closing(self._connect()) as db:
            rows = db.execute(
                f"SELECT * FROM key_requests WHERE {column} = ? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
        return [self._key_request(row) for row in rows]

    def _get_key_request(self, *, request_id: int) -> KeyRequest:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM key_requests WHERE id = ?", (request_id,)).fetchone()
        if row is None:
            raise MarketplaceNotFound("Key request was not found.")
        return self._key_request(row)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _email(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _user(row: sqlite3.Row | dict[str, Any]) -> UserAccount:
        return UserAccount(
            id=int(row["id"]),
            email=str(row["email"]),
            display_name=row["display_name"],
            premium_role=row["premium_role"],
            subscription_plan=row["subscription_plan"],
            subscription_status=row["subscription_status"],
            youtube_channel_id=row["youtube_channel_id"],
            youtube_google_subject=row["youtube_google_subject"],
            youtube_verified_at=row["youtube_verified_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _report_summary(row: sqlite3.Row | dict[str, Any]) -> ReportSummary:
        return ReportSummary(
            id=int(row["id"]),
            steam_url=str(row["steam_url"]),
            app_id=int(row["app_id"]),
            game_name=str(row["game_name"]),
            target_source=str(row["target_source"]),
            suggested_price_minor=row["suggested_price_minor"],
            price_currency=row["price_currency"],
            release_status=str(row["release_status"]),
            competitor_count=int(row["competitor_count"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _ownership_application(row: sqlite3.Row | dict[str, Any]) -> OwnershipApplication:
        return OwnershipApplication(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            report_id=int(row["report_id"]),
            app_id=int(row["app_id"]),
            game_name=str(row["game_name"]),
            steam_url=str(row["steam_url"]),
            studio_name=str(row["studio_name"]),
            applicant_name=str(row["applicant_name"]),
            applicant_title=str(row["applicant_title"]),
            business_email=str(row["business_email"]),
            company_website_url=row["company_website_url"],
            official_contact_url=row["official_contact_url"],
            steamworks_proof_url=row["steamworks_proof_url"],
            proof_url=row["proof_url"],
            proof_notes=str(row["proof_notes"]),
            status=row["status"],
            reviewed_notes=row["reviewed_notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _published_game(row: sqlite3.Row | dict[str, Any]) -> PublishedGame:
        return PublishedGame(
            id=int(row["id"]),
            owner_user_id=int(row["owner_user_id"]),
            ownership_application_id=int(row["ownership_application_id"]),
            app_id=int(row["app_id"]),
            game_name=str(row["game_name"]),
            steam_url=str(row["steam_url"]),
            pitch=str(row["pitch"]),
            contact_email=row["contact_email"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _key_request(row: sqlite3.Row | dict[str, Any]) -> KeyRequest:
        return KeyRequest(
            id=int(row["id"]),
            game_id=int(row["game_id"]),
            creator_user_id=int(row["creator_user_id"]),
            owner_user_id=int(row["owner_user_id"]),
            message=str(row["message"]),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
