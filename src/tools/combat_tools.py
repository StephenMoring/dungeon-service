"""The DM's start_encounter tool. The DM chooses who it is fighting; the server owns
every number from then on (combat_service)."""

from dataclasses import dataclass, field

from anthropic.types import ToolParam

from src.models.combat import Enemy

MAX_ENEMIES = 4
NAME_LENGTH = 60


@dataclass(frozen=True)
class EnemyType:
    """A bestiary entry as plain data, so it can travel with the turn after the
    request's database session is gone."""

    id: int
    key: str
    name: str
    description: str
    tier: int
    max_hp: int
    defense: int
    attack_bonus: int
    damage_dice: int
    damage_die: int
    damage_bonus: int

    @classmethod
    def from_row(cls, enemy: Enemy) -> "EnemyType":
        assert enemy.id is not None
        return cls(
            id=enemy.id,
            key=enemy.key,
            name=enemy.name,
            description=enemy.description,
            tier=enemy.tier,
            max_hp=enemy.max_hp,
            defense=enemy.defense,
            attack_bonus=enemy.attack_bonus,
            damage_dice=enemy.damage_dice,
            damage_die=enemy.damage_die,
            damage_bonus=enemy.damage_bonus,
        )


@dataclass(frozen=True)
class PlannedCombatant:
    enemy: EnemyType
    name: str


@dataclass
class EncounterPlan:
    """What the DM asked for. turn_service saves it with the turn's messages."""

    combatants: list[PlannedCombatant] = field(default_factory=list)

    def to_tool_result(self) -> str:
        if not self.combatants:
            return (
                "No fight started: none of those enemies exist. Continue the scene "
                "without a fight."
            )
        roster = "; ".join(f"{c.name} ({c.enemy.description})" for c in self.combatants)
        return (
            f"Encounter started against: {roster}. The server runs the fight from "
            "here. Describe the enemies and the moment before the clash. Do not "
            "narrate any blow, hit, miss or injury. End by asking what the player does."
        )


TIERS = {1: "minion", 2: "fighter", 3: "boss"}


def start_encounter_tool(bestiary: list[EnemyType]) -> ToolParam:
    roster = "\n".join(
        f"- {e.key}: {e.name}, {TIERS[e.tier]}. {e.description}" for e in bestiary
    )
    return {
        "name": "start_encounter",
        "description": (
            "Start a fight. Call it when combat breaks out: enemies attack, or the "
            "player attacks someone hostile. The server then runs the fight round by "
            "round (attacks, damage, hit points); you narrate each round's result. "
            "Pick 1-4 enemies that fit the scene and its danger. Bosses only for "
            "climaxes.\n\nBestiary:\n" + roster
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enemies": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_ENEMIES,
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": [e.key for e in bestiary],
                            },
                            "name": {
                                "type": "string",
                                "description": "Only for a notable individual, e.g. 'Grisk the One-Eyed'. Leave out for ordinary foes.",
                            },
                        },
                        "required": ["kind"],
                    },
                }
            },
            "required": ["enemies"],
        },
    }


def plan_encounter(bestiary: list[EnemyType], tool_input: dict) -> EncounterPlan:
    """Turn the DM's request into combatants. Unknown kinds are dropped and at most
    MAX_ENEMIES are kept; ordinary foes of the same kind are numbered."""
    by_key = {e.key: e for e in bestiary}
    requested = tool_input.get("enemies")
    if not isinstance(requested, list):
        return EncounterPlan()

    picked: list[tuple[EnemyType, str | None]] = []
    for entry in requested:
        if not isinstance(entry, dict) or entry.get("kind") not in by_key:
            continue
        name = entry.get("name")
        name = name.strip()[:NAME_LENGTH] if isinstance(name, str) else ""
        picked.append((by_key[entry["kind"]], name or None))
        if len(picked) == MAX_ENEMIES:
            break

    unnamed = [enemy.key for enemy, name in picked if name is None]
    seen: dict[str, int] = {}
    combatants = []
    for enemy, name in picked:
        if name is None:
            if unnamed.count(enemy.key) > 1:
                seen[enemy.key] = seen.get(enemy.key, 0) + 1
                name = f"{enemy.name} {seen[enemy.key]}"
            else:
                name = enemy.name
        combatants.append(PlannedCombatant(enemy=enemy, name=name))
    return EncounterPlan(combatants=combatants)
