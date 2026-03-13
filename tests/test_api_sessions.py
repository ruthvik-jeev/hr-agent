from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from apps.api import server
from apps.api.server import app, get_current_user


def _override_user():
    return {
        "employee_id": 201,
        "user_email": "alex.kim@acme.com",
        "name": "Alex Kim",
        "role": "EMPLOYEE",
        "department": "Engineering",
        "direct_reports": [],
        "is_manager": False,
    }


def _override_other_user():
    return {
        "employee_id": 212,
        "user_email": "emma.thompson@acme.com",
        "name": "Emma Thompson",
        "role": "EMPLOYEE",
        "department": "Engineering",
        "direct_reports": [],
        "is_manager": False,
    }


def test_session_turns_history_endpoint():
    app.dependency_overrides[get_current_user] = _override_user
    server._sessions.clear()
    server._sessions["session-1"] = {
        "user_email": "alex.kim@acme.com",
        "created_at": datetime.utcnow(),
        "turns": [
            {
                "query": "How many leave days do I have?",
                "response": "You have 18 days remaining.",
                "timestamp": "2026-03-13T09:00:00",
            },
            {
                "query": "Can I carry over days?",
                "response": "Yes, up to 5 days can be carried over.",
                "timestamp": "2026-03-13T09:01:00",
            },
        ],
        "pending_confirmation": None,
    }

    with TestClient(app) as client:
        response = client.get("/sessions/session-1/turns")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["query"] == "How many leave days do I have?"
        assert payload[1]["response"] == "Yes, up to 5 days can be carried over."

    app.dependency_overrides.clear()
    server._sessions.clear()


def test_session_turns_forbidden_and_not_found():
    server._sessions.clear()
    server._sessions["session-1"] = {
        "user_email": "alex.kim@acme.com",
        "created_at": datetime.utcnow(),
        "turns": [],
        "pending_confirmation": None,
    }

    app.dependency_overrides[get_current_user] = _override_other_user
    with TestClient(app) as client:
        forbidden = client.get("/sessions/session-1/turns")
        assert forbidden.status_code == 403

        missing = client.get("/sessions/missing/turns")
        assert missing.status_code == 404

    app.dependency_overrides.clear()
    server._sessions.clear()
