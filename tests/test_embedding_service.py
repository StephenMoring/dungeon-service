from unittest.mock import patch

from src.services.embedding_service import embed_query


@patch("src.services.embedding_service.voyageai.Client")
def test_embed_query_uses_query_input_type(client_cls):
    client_cls.return_value.embed.return_value.embeddings = [[0.1, 0.2]]

    vector = embed_query("I confront Mira")

    assert vector == [0.1, 0.2]
    client_cls.return_value.embed.assert_called_once_with(
        ["I confront Mira"], model="voyage-3.5", input_type="query"
    )
