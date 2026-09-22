from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import src.app as app_module
from src.app import activities, app


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


def test_signup_uses_activity_specific_lock_for_duplicate_check_and_append():
    # Arrange
    activity_name = "Art Club"
    email = "student@mergington.edu"
    original_activities = deepcopy(activities)
    original_lock = app_module.signup_locks[activity_name]
    original_participants = activities[activity_name]["participants"]
    events = []

    class RecordingLock:
        def __init__(self):
            self.locked = False

        def __enter__(self):
            self.locked = True
            events.append(("enter", self.locked))

        def __exit__(self, exc_type, exc, tb):
            events.append(("exit", self.locked))
            self.locked = False

    class RecordingParticipants(list):
        def __init__(self, lock):
            super().__init__()
            self.lock = lock

        def __contains__(self, item):
            events.append(("contains", self.lock.locked))
            return super().__contains__(item)

        def append(self, item):
            events.append(("append", self.lock.locked))
            super().append(item)

    recording_lock = RecordingLock()
    activities[activity_name]["participants"] = RecordingParticipants(recording_lock)
    app_module.signup_locks[activity_name] = recording_lock

    try:
        # Act
        response = app_module.signup_for_activity(activity_name, email)
    finally:
        activities[activity_name]["participants"] = original_participants
        app_module.signup_locks[activity_name] = original_lock
        activities.clear()
        activities.update(original_activities)

    # Assert
    assert response == {"message": f"Signed up {email} for {activity_name}"}
    assert events == [
        ("enter", True),
        ("contains", True),
        ("append", True),
        ("exit", True),
    ]


def test_signup_creates_lock_for_activity_added_after_import():
    # Arrange
    activity_name = "Debate Club"
    email = "student@mergington.edu"
    original_activities = deepcopy(activities)
    original_locks = dict(app_module.signup_locks)
    activities[activity_name] = {
        "description": "Practice debate and public speaking",
        "schedule": "Mondays, 4:00 PM - 5:00 PM",
        "max_participants": 16,
        "participants": [],
    }

    try:
        # Act
        response = app_module.signup_for_activity(activity_name, email)

        # Assert
        assert response == {"message": f"Signed up {email} for {activity_name}"}
        assert activity_name in app_module.signup_locks
    finally:
        app_module.signup_locks.clear()
        app_module.signup_locks.update(original_locks)
        activities.clear()
        activities.update(original_activities)


def test_signup_requires_email(client):
    # Arrange
    activity_name = "Art Club"

    # Act
    response = client.post(f"/activities/{activity_name}/signup")

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "email"]


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
