"""Combat rules and encounter persistence. Every number in a fight is decided here;
Claude only picks the enemies (start_encounter) and narrates each round.

Rules, on the 1-10 stat scale (5 is average):
- Hit points: 10 + 2 x endurance. 0 HP is death, for good.
- Defense: 10 + agility // 2 (+4 for a round spent defending).
- An attack hits when d20 + bonus >= the target's defense. A natural 1 always misses,
  a natural 20 always hits, and a critical hit (natural 20, or 19-20 with luck 8+)
  doubles the damage dice.
- The character attacks with their class's stat (or the better of strength and
  agility), for 1d8 + (stat - 4) // 2 damage.
- Fleeing: d20 + agility >= 10 + 2 per enemy still standing. Enemies don't attack a
  character who gets away.
- After the character acts, every enemy still standing attacks in turn.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlmodel import Session, col, select

from src.models.character import Character
from src.models.combat import Combatant, Encounter, Enemy
from src.tools.combat_tools import EncounterPlan, EnemyType
from src.tools.dice_tools import roll_d20, roll_die

Action = Literal["attack", "defend", "flee"]
Outcome = Literal["active", "won", "fled", "lost"]

DEFEND_BONUS = 4
PLAYER_DAMAGE_DIE = 8

ATTACK_STAT_BY_CLASS = {
    "warrior": "strength",
    "paladin": "strength",
    "rogue": "agility",
    "ranger": "agility",
    "monk": "agility",
    "mage": "intelligence",
    "warlock": "intelligence",
    "druid": "intelligence",
    "cleric": "intelligence",
    "bard": "charisma",
}


class NoActiveEncounter(Exception):
    pass


class InvalidTarget(Exception):
    pass


def _stat(value: int | None) -> int:
    return 5 if value is None else value


def max_hp_for(endurance: int | None) -> int:
    return 10 + 2 * _stat(endurance)


def defense_for(character: Character) -> int:
    return 10 + _stat(character.agility) // 2


def attack_stat(character: Character) -> str:
    stat = ATTACK_STAT_BY_CLASS.get(character.hero_class.strip().lower())
    if stat:
        return stat
    if _stat(character.agility) > _stat(character.strength):
        return "agility"
    return "strength"


def crit_range(luck: int | None) -> int:
    """The lowest natural roll that is a critical hit."""
    return 19 if _stat(luck) >= 8 else 20


@dataclass
class Attack:
    attacker: str
    target: str
    roll: int
    bonus: int
    total: int
    defense: int
    hit: bool
    crit: bool
    damage: int
    target_hp: int  # after the hit
    target_max_hp: int


@dataclass
class FleeAttempt:
    roll: int
    bonus: int
    total: int
    target: int
    success: bool


@dataclass
class RoundResult:
    round: int
    action: Action
    character: str
    attack: Attack | None = None
    flee: FleeAttempt | None = None
    defended: bool = False
    enemy_attacks: list[Attack] = field(default_factory=list)
    outcome: Outcome = "active"


def _attack(
    attacker: str,
    target: str,
    bonus: int,
    defense: int,
    dice: int,
    die: int,
    damage_bonus: int,
    target_hp: int,
    target_max_hp: int,
    crit_from: int = 20,
) -> Attack:
    roll = roll_d20()
    total = roll + bonus
    hit = roll != 1 and (roll == 20 or total >= defense)
    crit = hit and roll >= crit_from
    damage = 0
    if hit:
        rolled = sum(roll_die(die) for _ in range(dice * (2 if crit else 1)))
        damage = max(1, rolled + damage_bonus)
    return Attack(
        attacker=attacker,
        target=target,
        roll=roll,
        bonus=bonus,
        total=total,
        defense=defense,
        hit=hit,
        crit=crit,
        damage=damage,
        target_hp=max(0, target_hp - damage),
        target_max_hp=target_max_hp,
    )


def resolve_round(
    character: Character,
    encounter: Encounter,
    combatants: list[Combatant],
    enemies: dict[int, EnemyType],
    action: Action,
    target_id: int | None = None,
) -> RoundResult:
    """Play one round and apply the damage to the objects passed in. Raises
    InvalidTarget for an attack on an enemy who isn't standing in this fight."""
    standing = [c for c in combatants if c.current_hp > 0]
    target = None
    if action == "attack":
        if target_id is None:
            target = standing[0] if standing else None
        else:
            target = next((c for c in standing if c.id == target_id), None)
        if target is None:
            raise InvalidTarget("That enemy isn't standing in this fight.")

    encounter.round += 1
    result = RoundResult(round=encounter.round, action=action, character=character.name)
    defense = defense_for(character)

    if action == "attack":
        assert target is not None
        stat = attack_stat(character)
        stat_value = _stat(getattr(character, stat))
        result.attack = _attack(
            attacker=character.name,
            target=target.name,
            bonus=stat_value,
            defense=enemies[target.enemy_id].defense,
            dice=1,
            die=PLAYER_DAMAGE_DIE,
            damage_bonus=max(0, (stat_value - 4) // 2),
            target_hp=target.current_hp,
            target_max_hp=target.max_hp,
            crit_from=crit_range(character.luck),
        )
        target.current_hp = result.attack.target_hp
    elif action == "defend":
        result.defended = True
        defense += DEFEND_BONUS
    else:
        roll = roll_d20()
        bonus = _stat(character.agility)
        needed = 10 + 2 * len(standing)
        result.flee = FleeAttempt(
            roll=roll,
            bonus=bonus,
            total=roll + bonus,
            target=needed,
            success=roll + bonus >= needed,
        )
        if result.flee.success:
            result.outcome = "fled"
            return result

    for combatant in combatants:
        if combatant.current_hp <= 0:
            continue
        enemy = enemies[combatant.enemy_id]
        hit = _attack(
            attacker=combatant.name,
            target=character.name,
            bonus=enemy.attack_bonus,
            defense=defense,
            dice=enemy.damage_dice,
            die=enemy.damage_die,
            damage_bonus=enemy.damage_bonus,
            target_hp=character.current_hp,
            target_max_hp=character.max_hp,
        )
        character.current_hp = hit.target_hp
        result.enemy_attacks.append(hit)
        if character.current_hp == 0:
            result.outcome = "lost"
            return result

    if all(c.current_hp <= 0 for c in combatants):
        result.outcome = "won"
    return result


def describe_action(result: RoundResult) -> str:
    """The player's line in the message history for a combat button."""
    if result.action == "defend":
        return "I raise my guard and defend."
    if result.action == "flee":
        return "I try to escape."
    assert result.attack is not None
    return f"I attack {result.attack.target}."


# Persistence


def load_bestiary(session: Session) -> list[EnemyType]:
    enemies = session.exec(select(Enemy).order_by(col(Enemy.tier), col(Enemy.id)))
    return [EnemyType.from_row(e) for e in enemies.all()]


def active_encounter(
    session: Session, character_id: int, lock: bool = False
) -> Encounter | None:
    statement = select(Encounter).where(
        Encounter.character_id == character_id, Encounter.status == "active"
    )
    if lock:
        statement = statement.with_for_update()
    return session.exec(statement).first()


def combatants_of(session: Session, encounter_id: int) -> list[Combatant]:
    return list(
        session.exec(
            select(Combatant)
            .where(Combatant.encounter_id == encounter_id)
            .order_by(col(Combatant.position))
        ).all()
    )


def begin_encounter(
    session: Session, campaign_id: int, character_id: int, plan: EncounterPlan
) -> Encounter:
    """Add an encounter and its combatants to the session (the caller commits)."""
    encounter = Encounter(campaign_id=campaign_id, character_id=character_id)
    session.add(encounter)
    session.flush()
    assert encounter.id is not None
    for position, planned in enumerate(plan.combatants):
        session.add(
            Combatant(
                encounter_id=encounter.id,
                enemy_id=planned.enemy.id,
                name=planned.name,
                position=position,
                max_hp=planned.enemy.max_hp,
                current_hp=planned.enemy.max_hp,
            )
        )
    session.flush()
    return encounter


def encounter_state(
    encounter: Encounter,
    combatants: list[Combatant],
    character: Character,
    enemies: dict[int, EnemyType],
) -> dict:
    """The fight as the UI shows it (the `combat` SSE event and GET .../encounter)."""
    return {
        "id": encounter.id,
        "status": encounter.status,
        "round": encounter.round,
        "enemies": [
            {
                "id": c.id,
                "name": c.name,
                "kind": enemies[c.enemy_id].key,
                "hp": c.current_hp,
                "max_hp": c.max_hp,
            }
            for c in combatants
        ],
        "player": {
            "hp": character.current_hp,
            "max_hp": character.max_hp,
            "defense": defense_for(character),
            "dead": character.died_at is not None,
        },
    }


def bestiary_by_id(bestiary: list[EnemyType]) -> dict[int, EnemyType]:
    return {e.id: e for e in bestiary}


def play_round(
    session: Session,
    character: Character,
    bestiary: list[EnemyType],
    action: Action,
    target_id: int | None = None,
) -> tuple[RoundResult, dict]:
    """Resolve one round of the character's active fight and commit it, before any
    narration: refreshing the page or a failed narration can't undo or reroll it.
    Returns the round and the encounter state after it."""
    assert character.id is not None
    # Lock the fight, so two clicks play two rounds one after another rather than
    # both starting from the same hit points.
    encounter = active_encounter(session, character.id, lock=True)
    if encounter is None:
        raise NoActiveEncounter("There's no fight going on.")
    assert encounter.id is not None
    session.refresh(character)
    combatants = combatants_of(session, encounter.id)
    enemies = bestiary_by_id(bestiary)

    result = resolve_round(character, encounter, combatants, enemies, action, target_id)

    now = datetime.now(UTC)
    if result.outcome != "active":
        encounter.status = result.outcome
        encounter.ended_at = now
    if result.outcome == "lost":
        character.died_at = now
    session.add(encounter)
    session.add(character)
    for combatant in combatants:
        session.add(combatant)
    session.commit()
    return result, encounter_state(encounter, combatants, character, enemies)


def current_state(
    session: Session, character: Character, bestiary: list[EnemyType]
) -> dict | None:
    """The character's active fight, or None."""
    assert character.id is not None
    encounter = active_encounter(session, character.id)
    if encounter is None or encounter.id is None:
        return None
    return encounter_state(
        encounter,
        combatants_of(session, encounter.id),
        character,
        bestiary_by_id(bestiary),
    )
