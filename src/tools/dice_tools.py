import random
from dataclasses import dataclass

from anthropic.types import ToolParam

from src.models.character import Character

STATS = [
    "strength",
    "perception",
    "endurance",
    "charisma",
    "intelligence",
    "agility",
    "luck",
]

DIFFICULTY_TARGETS: dict[str, int] = {"easy": 10, "medium": 15, "hard": 20}

roll_check_tool: ToolParam = {
    "name": "roll_check",
    "description": "Roll a d20 and add the character's stat to decide whether an action succeeds. Use only when the outcome is uncertain and failure would matter. Never for routine actions. The result is final.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stat": {
                "type": "string",
                "enum": STATS,
                "description": "The single stat that best fits the action, e.g. agility for sneaking",
            },
            "difficulty": {
                "type": "string",
                "enum": list(DIFFICULTY_TARGETS),
                "description": "easy (10), medium (15), or hard (20)",
            },
            "reason": {
                "type": "string",
                "description": "Short description of what is being attempted, e.g. 'sneaking past alert guards'",
            },
        },
        "required": ["stat", "difficulty", "reason"],
    },
}


@dataclass
class RollResult:
    stat: str
    stat_value: int
    roll: int
    total: int
    difficulty: str
    target: int
    success: bool
    reason: str

    def to_tool_result(self) -> str:
        outcome = "SUCCESS" if self.success else "FAILURE"
        return (
            f"{outcome}. {self.stat} check ({self.difficulty}): "
            f"rolled {self.roll} + {self.stat_value} = {self.total} vs {self.target}."
        )


def roll_d20() -> int:
    return random.randint(1, 20)


def handle_roll_check(
    character: Character, stat: str, difficulty: str, reason: str
) -> RollResult:
    stat_value = getattr(character, stat) or 0
    roll = roll_d20()
    total = roll + stat_value
    target = DIFFICULTY_TARGETS[difficulty]
    return RollResult(
        stat=stat,
        stat_value=stat_value,
        roll=roll,
        total=total,
        difficulty=difficulty,
        target=target,
        success=total >= target,
        reason=reason,
    )
