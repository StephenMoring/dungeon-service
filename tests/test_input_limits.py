"""Player input is checked before it reaches the database or Claude: stats stay on
the 1-10 scale the dice use, and free text has a length cap, so a pasted novel can't
run up the Claude bill."""

import pytest

from tests.test_characters import CHARACTER_BODY, PREVIEW_BODY


@pytest.mark.parametrize("value", [0, 11, 999, -3])
def test_stats_must_be_one_to_ten(client, value):
    response = client.post("/characters/", json={**CHARACTER_BODY, "strength": value})

    assert response.status_code == 422


def test_every_stat_is_required(client):
    body = {k: v for k, v in CHARACTER_BODY.items() if k != "luck"}

    assert client.post("/characters/", json=body).status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "x" * 61),
        ("description", "x" * 2001),
        ("biography", "x" * 4001),
        ("age", 0),
        ("age", 1001),
    ],
)
def test_character_fields_are_bounded(client, field, value):
    response = client.post("/characters/", json={**CHARACTER_BODY, field: value})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "x" * 61), ("description", "x" * 2001), ("race", "x" * 41)],
)
def test_preview_input_is_bounded(client, field, value):
    response = client.post("/characters/preview", json={**PREVIEW_BODY, field: value})

    assert response.status_code == 422


@pytest.mark.parametrize("message", ["", "x" * 2001])
def test_turn_message_is_bounded(client, session, message):
    response = client.post("/characters/1/turns/stream", json={"message": message})

    assert response.status_code == 422


@pytest.mark.parametrize("description", ["", "x" * 2001])
def test_campaign_description_is_bounded(client, description):
    response = client.post(
        "/campaigns/", json={"character_id": 1, "description": description}
    )

    assert response.status_code == 422
