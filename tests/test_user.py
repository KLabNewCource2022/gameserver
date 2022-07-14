from fastapi.testclient import TestClient

from app import model
from app.api import app

client = TestClient(app)


def test_create_user():
    response = client.post(
        "/user/create", json={"user_name": "test1", "leader_card_id": 1000}
    )
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"user_token"}

    token = response.json()["user_token"]

    response = client.get("/user/me", headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200

    response_data = response.json()
    assert response_data.keys() == {"id", "name", "leader_card_id"}
    assert response_data["name"] == "test1"
    assert response_data["leader_card_id"] == 1000


def test_update_user():
    token = model.create_user("update_test", 42)

    response = client.post(
        "/user/update",
        headers={"Authorization": f"bearer {token}"},
        json={"user_name": "update_test2", "leader_card_id": 1000},
    )
    assert response.status_code == 200

    user = model.get_user_by_token(token)
    assert user is not None
    assert user.name == "update_test2"
    assert user.leader_card_id == 1000
