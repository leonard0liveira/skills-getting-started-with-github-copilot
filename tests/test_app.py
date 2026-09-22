from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import activities, app, signup_for_activity


@pytest.fixture
def client():
    original_activities = deepcopy(activities)

    with TestClient(app) as test_client:
        yield test_client

    activities.clear()
    activities.update(original_activities)


def test_root_redirects_to_static_index(client):
    # Arrange
    expected_location = "/static/index.html"

    # Act
    response = client.get("/", follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == expected_location


def test_static_index_is_served(client):
    # Arrange
    static_index_path = "/static/index.html"

    # Act
    response = client.get(static_index_path)

    # Assert
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_activities_returns_expected_activity_data(client):
    # Arrange
    expected_activity_names = {
        "Chess Club",
        "Programming Class",
        "Gym Class",
        "Art Club",
        "Drama Club",
    }

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert set(response.json()) == expected_activity_names
    for activity in response.json().values():
        assert set(activity) == {
            "description",
            "schedule",
            "max_participants",
            "participants",
        }


def test_signup_adds_student_to_activity(client):
    # Arrange
    activity_name = "Art Club"
    email = "student@mergington.edu"

    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Signed up {email} for {activity_name}"
    }
    assert email in activities[activity_name]["participants"]


def test_signup_returns_not_found_for_unknown_activity(client):
    # Arrange
    activity_name = "Unknown Club"
    email = "student@mergington.edu"

    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_signup_rejects_duplicate_student(client):
    # Arrange
    activity_name = "Chess Club"
    email = activities[activity_name]["participants"][0]

    # Act
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Student is already signed up for this activity"
    }


def test_signup_requires_email(client):
    # Arrange
    activity_name = "Art Club"

    # Act
    response = client.post(f"/activities/{activity_name}/signup")

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "email"]


def test_signup_prevents_duplicate_concurrent_signups():
    # Arrange
    activity_name = "Art Club"
    email = "student@mergington.edu"

    class CoordinatedParticipants(list):
        def __init__(self):
            super().__init__()
            self.call_count = 0
            self.call_count_lock = threading.Lock()
            self.first_check = threading.Event()
            self.second_check = threading.Event()

        def __contains__(self, item):
            with self.call_count_lock:
                self.call_count += 1
                call_number = self.call_count

            if call_number == 1:
                self.first_check.set()
                self.second_check.wait(timeout=0.1)
            elif call_number == 2:
                self.second_check.set()
                self.first_check.wait(timeout=0.1)

            return super().__contains__(item)

    original_participants = activities[activity_name]["participants"]
    participants = CoordinatedParticipants()
    activities[activity_name]["participants"] = participants

    def attempt_signup():
        try:
            return signup_for_activity(activity_name, email)
        except HTTPException as exc:
            return exc

    try:
        # Act
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt_signup(), range(2)))

        # Assert
        assert sum(result == {"message": f"Signed up {email} for {activity_name}"} for result in results) == 1
        assert sum(
            isinstance(result, HTTPException)
            and result.status_code == 400
            and result.detail == "Student is already signed up for this activity"
            for result in results
        ) == 1
        assert participants.count(email) == 1
    finally:
        activities[activity_name]["participants"] = original_participants


def test_remove_participant_removes_student_from_activity(client):
    # Arrange
    activity_name = "Chess Club"
    email = activities[activity_name]["participants"][0]

    # Act
    response = client.delete(
        f"/activities/{activity_name}/participants",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Removed {email} from {activity_name}"
    }
    assert email not in activities[activity_name]["participants"]


def test_remove_participant_returns_not_found_for_unknown_activity(client):
    # Arrange
    activity_name = "Unknown Club"
    email = "student@mergington.edu"

    # Act
    response = client.delete(
        f"/activities/{activity_name}/participants",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_remove_participant_returns_not_found_for_unknown_student(client):
    # Arrange
    activity_name = "Chess Club"
    email = "student@mergington.edu"

    # Act
    response = client.delete(
        f"/activities/{activity_name}/participants",
        params={"email": email},
    )

    # Assert
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Student is not signed up for this activity"
    }


def test_remove_participant_requires_email(client):
    # Arrange
    activity_name = "Chess Club"

    # Act
    response = client.delete(f"/activities/{activity_name}/participants")

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "email"]
