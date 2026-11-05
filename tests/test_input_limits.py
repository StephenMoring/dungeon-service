"""Player input is checked before it reaches the database or Claude: free text has a
length cap, so a pasted novel can't run up the Claude bill. Stats are never player
input: they come from the server-signed preview (see test_character_service)."""

import pytest

from tests.test_characters import PREVIEW_BODY


def test_preview_token_is_bounded(client):
    response = client.post("/characters/", json={"preview_token": "x" * 8001})

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
