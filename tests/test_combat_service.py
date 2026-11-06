from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from src.models.combat import Combatant, Encounter
from src.services.combat_service import (
    InvalidTarget,
    NoActiveEncounter,
    attack_stat,
    crit_range,
    defense_for,
    describe_action,
    encounter_state,
    max_hp_for,
    play_round,
    resolve_round,
)
from src.tools.combat_tools import EnemyType
from tests.conftest import make_character

GOBLIN = EnemyType(
    id=2,
    key="goblin",
    name="Goblin",
    description="A small raider.",
    tier=1,
    max_hp=7,
    defense=11,
    attack_bonus=3,
    damage_dice=1,
    damage_die=6,
    damage_bonus=0,
)
ENEMIES = {GOBLIN.id: GOBLIN}


@contextmanager
def dice(d20s: list[int], dies: list[int] = ()):
    """Fix the rolls, in order. Fails if the code rolls more than given."""
    with (
        patch("src.services.combat_service.roll_d20", side_effect=list(d20s)),
        patch("src.services.combat_service.roll_die", side_effect=list(dies)),
    ):
        yield


def fighter(**kwargs):
    # Warrior: attacks with strength 7 (+1 damage), agility 4 -> defense 12, 18 HP.
    defaults = {
        "hero_class": "Warrior",
        "strength": 7,
        "agility": 4,
        "endurance": 4,
        "luck": 5,
        "max_hp": 18,
        "current_hp": 18,
    }
    defaults.update(kwargs)
    return make_character(**defaults)


def goblins(*hps: int) -> list[Combatant]:
    return [
        Combatant(
            id=10 + i,
            encounter_id=1,
            enemy_id=GOBLIN.id,
            name=f"Goblin {i + 1}",
            position=i,
            max_hp=7,
            current_hp=hp,
        )
        for i, hp in enumerate(hps)
    ]


def fight():
    return Encounter(id=1, campaign_id=1, character_id=1)


class TestCharacterNumbers:
    @pytest.mark.parametrize("endurance, hp", [(1, 12), (5, 20), (10, 30), (None, 20)])
    def test_max_hp_comes_from_endurance(self, endurance, hp):
        assert max_hp_for(endurance) == hp

    @pytest.mark.parametrize("agility, defense", [(1, 10), (5, 12), (10, 15)])
    def test_defense_comes_from_agility(self, agility, defense):
        assert defense_for(make_character(agility=agility)) == defense

    @pytest.mark.parametrize(
        "hero_class, stat",
        [
            ("Warrior", "strength"),
            ("rogue", "agility"),
            (" Mage ", "intelligence"),
            ("Bard", "charisma"),
        ],
    )
    def test_attack_stat_follows_class(self, hero_class, stat):
        assert attack_stat(make_character(hero_class=hero_class)) == stat

    def test_unknown_class_uses_the_better_of_strength_and_agility(self):
        assert (
            attack_stat(make_character(hero_class="Pirate", strength=3, agility=8))
            == "agility"
        )
        assert (
            attack_stat(make_character(hero_class="Pirate", strength=8, agility=3))
            == "strength"
        )

    def test_lucky_characters_crit_more_often(self):
        assert crit_range(5) == 20
        assert crit_range(8) == 19


class TestAttack:
    def test_hit_damages_the_target_then_enemies_attack(self):
        character, enemies = fighter(), goblins(7)

        # Player rolls 5 + 7 = 12 vs 11: hit for 6 + 1. Goblin rolls 9 + 3 = 12 vs 12: hit for 4.
        with dice([5, 9], [6, 4]):
            result = resolve_round(character, fight(), enemies, ENEMIES, "attack")

        assert result.attack is not None
        assert (result.attack.total, result.attack.hit, result.attack.damage) == (
            12,
            True,
            7,
        )
        assert enemies[0].current_hp == 0
        assert result.enemy_attacks == []  # it fell before it could swing
        assert result.outcome == "won"

    def test_enemies_still_standing_attack_back(self):
        character, enemies = fighter(), goblins(7, 7)

        # Player misses (3 + 7 = 10 vs 11); both goblins attack: 9+3 hits for 4, 2+3 misses.
        with dice([3, 9, 2], [4]):
            result = resolve_round(character, fight(), enemies, ENEMIES, "attack")

        assert result.attack is not None and not result.attack.hit
        assert [a.hit for a in result.enemy_attacks] == [True, False]
        assert character.current_hp == 14
        assert result.enemy_attacks[0].target_hp == 14
        assert result.outcome == "active"
        assert result.round == 1

    def test_attacks_the_chosen_target(self):
        character, enemies = fighter(), goblins(7, 7)

        with dice([20, 1], [3, 3]):
            result = resolve_round(
                character, fight(), enemies, ENEMIES, "attack", target_id=11
            )

        assert result.attack is not None and result.attack.target == "Goblin 2"
        assert [e.current_hp for e in enemies] == [7, 0]

    def test_cannot_target_a_fallen_enemy(self):
        with pytest.raises(InvalidTarget):
            resolve_round(
                fighter(), fight(), goblins(0, 7), ENEMIES, "attack", target_id=10
            )

    def test_cannot_target_an_enemy_from_another_fight(self):
        with pytest.raises(InvalidTarget):
            resolve_round(
                fighter(), fight(), goblins(7), ENEMIES, "attack", target_id=999
            )

    def test_natural_one_always_misses(self):
        character = fighter(strength=10)

        with dice([1, 1]):  # 1 + 10 = 11 would beat defense 11
            result = resolve_round(character, fight(), goblins(7), ENEMIES, "attack")

        assert result.attack is not None and not result.attack.hit

    def test_natural_twenty_crits_and_doubles_the_dice(self):
        character = fighter(strength=1)  # damage bonus 0

        with dice([20, 1], [2, 3]):
            result = resolve_round(character, fight(), goblins(7), ENEMIES, "attack")

        assert result.attack is not None
        assert result.attack.crit
        assert result.attack.damage == 5

    def test_damage_is_at_least_one(self):
        orc = EnemyType(**{**GOBLIN.__dict__, "damage_bonus": -3})
        character = fighter()

        with dice([1, 15], [1]):
            result = resolve_round(
                character, fight(), goblins(7), {orc.id: orc}, "attack"
            )

        assert result.enemy_attacks[0].damage == 1


class TestDefendAndFlee:
    def test_defending_makes_the_character_harder_to_hit(self):
        character = fighter()  # defense 12, 16 while defending

        with dice([12]):  # 12 + 3 = 15: would hit, misses a defender
            result = resolve_round(character, fight(), goblins(7), ENEMIES, "defend")

        assert result.defended
        assert result.attack is None
        assert result.enemy_attacks[0].defense == 16
        assert not result.enemy_attacks[0].hit

    def test_escaping_ends_the_fight_without_enemy_attacks(self):
        character = fighter()  # agility 4; two goblins: needs 14

        with dice([10]):
            result = resolve_round(character, fight(), goblins(7, 7), ENEMIES, "flee")

        assert result.flee is not None
        assert (result.flee.total, result.flee.target, result.flee.success) == (
            14,
            14,
            True,
        )
        assert result.enemy_attacks == []
        assert result.outcome == "fled"

    def test_failed_escape_lets_enemies_attack(self):
        with dice([2, 1, 1]):
            result = resolve_round(fighter(), fight(), goblins(7, 7), ENEMIES, "flee")

        assert result.flee is not None and not result.flee.success
        assert len(result.enemy_attacks) == 2
        assert result.outcome == "active"


class TestDeath:
    def test_zero_hp_loses_the_fight_and_stops_further_attacks(self):
        character = fighter(current_hp=3)

        # Player misses; goblin 1 hits for 5 (HP floors at 0); goblin 2 never swings.
        with dice([2, 15], [5]):
            result = resolve_round(character, fight(), goblins(7, 7), ENEMIES, "attack")

        assert character.current_hp == 0
        assert len(result.enemy_attacks) == 1
        assert result.enemy_attacks[0].target_hp == 0
        assert result.outcome == "lost"


class TestDescribeAction:
    def test_names_the_target(self):
        with dice([5, 1], [1]):
            result = resolve_round(fighter(), fight(), goblins(7), ENEMIES, "attack")

        assert describe_action(result) == "I attack Goblin 1."


class TestEncounterState:
    def test_shows_enemies_and_the_player(self):
        character = fighter(current_hp=11)

        state = encounter_state(fight(), goblins(3), character, ENEMIES)

        assert state["enemies"] == [
            {"id": 10, "name": "Goblin 1", "kind": "goblin", "hp": 3, "max_hp": 7}
        ]
        assert state["player"] == {
            "hp": 11,
            "max_hp": 18,
            "defense": 12,
            "dead": False,
        }


class TestPlayRound:
    def session_with(self, encounter, combatants):
        session = MagicMock()
        session.exec.return_value.first.return_value = encounter
        session.exec.return_value.all.return_value = combatants
        return session

    def test_saves_the_round_before_narration(self):
        character, enemies = fighter(), goblins(7)
        encounter = fight()
        session = self.session_with(encounter, enemies)

        with dice([5, 9], [6, 4]):
            result, state = play_round(session, character, [GOBLIN], "attack")

        assert result.outcome == "won"
        assert encounter.status == "won"
        assert encounter.ended_at is not None
        assert state["status"] == "won"
        session.commit.assert_called_once()

    def test_locks_the_fight_and_rereads_the_character(self):
        session = self.session_with(fight(), goblins(7))
        character = fighter()

        with dice([5, 9], [6, 4]):
            play_round(session, character, [GOBLIN], "attack")

        lookup = session.exec.call_args_list[0].args[0]
        assert lookup._for_update_arg is not None
        session.refresh.assert_called_once_with(character)

    def test_death_is_recorded_on_the_character(self):
        character = fighter(current_hp=1)
        encounter = fight()
        session = self.session_with(encounter, goblins(7))

        with dice([2, 15], [5]):
            play_round(session, character, [GOBLIN], "attack")

        assert character.died_at is not None
        assert encounter.status == "lost"

    def test_without_a_fight_nothing_is_saved(self):
        session = self.session_with(None, [])

        with pytest.raises(NoActiveEncounter):
            play_round(session, fighter(), [GOBLIN], "attack")

        session.commit.assert_not_called()

    def test_bad_target_saves_nothing(self):
        session = self.session_with(fight(), goblins(7))

        with pytest.raises(InvalidTarget):
            play_round(session, fighter(), [GOBLIN], "attack", target_id=999)

        session.commit.assert_not_called()
