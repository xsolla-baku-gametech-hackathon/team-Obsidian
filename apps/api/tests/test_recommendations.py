from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from ili_api.main import create_app


def test_recommendation_endpoint_and_validation():
    now = datetime.now(UTC)
    start = now.date()
    payload = {
        "game": {"name": "Synthetic API fixture", "genres": ["Strategy"]},
        "earliest_date": start.isoformat(),
        "latest_date": (start + timedelta(days=30)).isoformat(),
        "dataset": {
            "dataset_id": "synthetic-empty-fixture",
            "collected_at": now.isoformat(),
            "games": [],
            "coverage": {
                "horizon_start": start.isoformat(),
                "horizon_end": (start + timedelta(days=31)).isoformat(),
                "discovery_method": "test",
                "notes": "Empty synthetic test dataset",
            },
        },
    }
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/recommendations", json=payload)
        assert response.status_code == 200
        assert response.json()["model_type"] == "explainable_baseline"
        assert response.json()["release"]["status"] == "insufficient_evidence"
        assert response.json()["price"]["suggested_price_minor"] is None
        payload["latest_date"] = start.isoformat()
        invalid = client.post("/api/v1/recommendations", json=payload)
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"
