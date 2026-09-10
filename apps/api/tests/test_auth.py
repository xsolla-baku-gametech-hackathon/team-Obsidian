from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from fastapi.testclient import TestClient
from ili_api.main import create_app
from ili_core.storage.users import UserStore


@contextmanager
def auth_client(tmp_path) -> Iterator[TestClient]:
    store = UserStore(tmp_path / "users.sqlite", session_ttl=timedelta(hours=1))
    with TestClient(create_app(user_store=store)) as test_client:
        yield test_client


def signup(test_client: TestClient, email: str = "dev@example.com") -> dict:
    response = test_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secure-password", "display_name": "Dev User"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_signup_login_me_logout(tmp_path):
    with auth_client(tmp_path) as test_client:
        session = signup(test_client)
        assert session["token_type"] == "bearer"
        assert session["user"]["subscription_status"] == "inactive"

        duplicate = test_client.post(
            "/api/v1/auth/signup",
            json={"email": "DEV@example.com", "password": "secure-password"},
        )
        assert duplicate.status_code == 409

        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "dev@example.com", "password": "secure-password"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "dev@example.com"

        logout = test_client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert logout.status_code == 204
        after_logout = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert after_logout.status_code == 401


def test_subscription_roles_and_youtube_verification(tmp_path):
    with auth_client(tmp_path) as test_client:
        session = signup(test_client, email="creator@example.com")
        token = session["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        subscribe = test_client.post(
            "/api/v1/auth/subscription",
            json={"plan": "pro", "role": "content_creator"},
            headers=headers,
        )
        assert subscribe.status_code == 200
        assert subscribe.json()["premium_role"] == "content_creator"
        assert subscribe.json()["subscription_status"] == "pending_youtube_verification"

        verified = test_client.post(
            "/api/v1/auth/youtube/dev-verify",
            json={"channel_id": "UC123456789", "google_subject": "google-oauth-subject"},
            headers=headers,
        )
        assert verified.status_code == 200
        assert verified.json()["subscription_status"] == "active"
        assert verified.json()["youtube_channel_id"] == "UC123456789"


def test_game_developer_subscription_is_active_immediately(tmp_path):
    with auth_client(tmp_path) as test_client:
        session = signup(test_client)
        response = test_client.post(
            "/api/v1/auth/subscription",
            json={"plan": "starter", "role": "game_developer"},
            headers={"Authorization": f"Bearer {session['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["premium_role"] == "game_developer"
        assert response.json()["subscription_status"] == "active"
