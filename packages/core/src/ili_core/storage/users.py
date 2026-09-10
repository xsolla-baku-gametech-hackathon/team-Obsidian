"""SQLite-backed user and session store."""

import hashlib
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


class AuthConflict(Exception):
    pass


class AuthInvalidCredentials(Exception):
    pass


class AuthUnauthorized(Exception):
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
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

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
