from src.tools.combat_tools import (
    MAX_ENEMIES,
    EncounterPlan,
    plan_encounter,
    start_encounter_tool,
)
from tests.test_combat_service import GOBLIN

WOLF = GOBLIN.__class__(**{**GOBLIN.__dict__, "id": 3, "key": "wolf", "name": "Wolf"})
BESTIARY = [GOBLIN, WOLF]


def names(plan: EncounterPlan) -> list[str]:
    return [c.name for c in plan.combatants]


class TestTool:
    def test_kinds_are_limited_to_the_bestiary(self):
        tool = start_encounter_tool(BESTIARY)

        item = tool["input_schema"]["properties"]["enemies"]["items"]
        assert item["properties"]["kind"]["enum"] == ["goblin", "wolf"]
        assert tool["input_schema"]["properties"]["enemies"]["maxItems"] == MAX_ENEMIES

    def test_description_lists_the_bestiary(self):
        description = start_encounter_tool(BESTIARY)["description"]

        assert "- goblin: Goblin, minion. A small raider." in description


class TestPlanEncounter:
    def test_numbers_ordinary_foes_of_the_same_kind(self):
        plan = plan_encounter(
            BESTIARY,
            {"enemies": [{"kind": "goblin"}, {"kind": "wolf"}, {"kind": "goblin"}]},
        )

        assert names(plan) == ["Goblin 1", "Wolf", "Goblin 2"]
        assert plan.combatants[1].enemy is WOLF

    def test_keeps_names_the_dm_gave(self):
        plan = plan_encounter(
            BESTIARY,
            {"enemies": [{"kind": "goblin", "name": " Grisk "}, {"kind": "goblin"}]},
        )

        assert names(plan) == ["Grisk", "Goblin"]

    def test_drops_unknown_kinds_and_caps_the_count(self):
        plan = plan_encounter(
            BESTIARY,
            {"enemies": [{"kind": "dragon"}] + [{"kind": "goblin"}] * 9},
        )

        assert len(plan.combatants) == MAX_ENEMIES

    def test_long_names_are_cut(self):
        plan = plan_encounter(
            BESTIARY, {"enemies": [{"kind": "wolf", "name": "x" * 500}]}
        )

        assert len(plan.combatants[0].name) == 60

    def test_nothing_valid_starts_no_fight(self):
        plan = plan_encounter(BESTIARY, {"enemies": [{"kind": "dragon"}]})

        assert plan.combatants == []
        assert "No fight started" in plan.to_tool_result()

    def test_malformed_input_starts_no_fight(self):
        assert plan_encounter(BESTIARY, {"enemies": "goblins"}).combatants == []

    def test_tool_result_tells_the_dm_not_to_narrate_blows(self):
        result = plan_encounter(BESTIARY, {"enemies": [{"kind": "goblin"}]})

        text = result.to_tool_result()
        assert "Goblin (A small raider.)" in text
        assert "Do not narrate any blow" in text
