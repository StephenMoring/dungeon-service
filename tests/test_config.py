import pytest

from src.config.config import require_secret_key


def test_refuses_a_short_secret_key():
    # A short HS256 key can be brute-forced, which would let anyone sign a session
    # (or a character preview) for any player.
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        require_secret_key("fourteen-bytes")


def test_accepts_a_long_secret_key():
    key = "x" * 32
    assert require_secret_key(key) == key
