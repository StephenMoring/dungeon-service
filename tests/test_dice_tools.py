from unittest.mock import patch

import pytest

from src.tools.dice_tools import handle_roll_check, roll_check_tool, roll_d20
from tests.conftest import make_character

STATS = [
    "strength",
    "perception",
    "endurance",
    "charisma",
    "intelligence",
    "agility",
    "luck",
]


@patch("src.tools.dice_tools.roll_d20", return_value=7)
def test_adds_stat_to_roll(_):
    result = handle_roll_check(make_character(agility=6), "agility", "hard", "sneak")

    assert result.stat_value == 6
    assert result.roll == 7
    assert result.total == 13
    assert result.target == 20
    assert result.success is False


@pytest.mark.parametrize(
    "difficulty, target", [("easy", 10), ("medium", 15), ("hard", 20)]
)
@patch("src.tools.dice_tools.roll_d20", return_value=1)
def test_targets_per_difficulty(_, difficulty, target):
    result = handle_roll_check(make_character(), "luck", difficulty, "test")

    assert result.target == target
    assert result.difficulty == difficulty


@patch("src.tools.dice_tools.roll_d20", return_value=10)
def test_tie_passes(_):
    result = handle_roll_check(make_character(agility=5), "agility", "medium", "jump")

    assert result.total == 15
    assert result.success is True


@patch("src.tools.dice_tools.roll_d20", return_value=12)
def test_none_stat_counts_as_zero(_):
    result = handle_roll_check(make_character(luck=None), "luck", "easy", "coin")

    assert result.stat_value == 0
    assert result.total == 12


def test_tool_result_states_outcome():
    with patch("src.tools.dice_tools.roll_d20", return_value=7):
        fail = handle_roll_check(make_character(agility=6), "agility", "hard", "sneak")
    with patch("src.tools.dice_tools.roll_d20", return_value=20):
        win = handle_roll_check(make_character(agility=6), "agility", "hard", "sneak")

    assert (
        fail.to_tool_result()
        == "FAILURE. agility check (hard): rolled 7 + 6 = 13 vs 20."
    )
    assert win.to_tool_result().startswith("SUCCESS.")


def test_roll_d20_in_range():
    rolls = {roll_d20() for _ in range(200)}

    assert rolls <= set(range(1, 21))
    assert len(rolls) > 1


def test_tool_schema_lists_all_stats():
    props = roll_check_tool["input_schema"]["properties"]

    assert roll_check_tool["name"] == "roll_check"
    assert props["stat"]["enum"] == STATS
    assert props["difficulty"]["enum"] == ["easy", "medium", "hard"]
    assert set(roll_check_tool["input_schema"]["required"]) == {
        "stat",
        "difficulty",
        "reason",
    }
