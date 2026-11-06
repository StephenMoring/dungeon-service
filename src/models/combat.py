from datetime import UTC, datetime
from typing import Literal

from sqlmodel import Field, SQLModel


class Enemy(SQLModel, table=True):
    """A bestiary entry (shared game content, seeded by V6__combat.sql). The DM picks
    enemies by `key`; an attack hits when d20 + attack_bonus >= the target's defense
    and deals damage_dice d damage_die + damage_bonus."""

    id: int | None = Field(default=None, primary_key=True)
    key: str
    name: str
    description: str
    tier: int  # 1 minion, 2 fighter, 3 boss
    max_hp: int
    defense: int
    attack_bonus: int
    damage_dice: int
    damage_die: int
    damage_bonus: int = 0


class Encounter(SQLModel, table=True):
    """One fight. status: active, won, fled, lost (the character died)."""

    id: int | None = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    character_id: int = Field(foreign_key="character.id")
    status: str = "active"
    round: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None


class Combatant(SQLModel, table=True):
    """An enemy in one encounter, with its own name and hit points."""

    id: int | None = Field(default=None, primary_key=True)
    encounter_id: int = Field(foreign_key="encounter.id")
    enemy_id: int = Field(foreign_key="enemy.id")
    name: str
    position: int
    max_hp: int
    current_hp: int


class CombatActionRequest(SQLModel):
    """A combat button. `target_id` is a combatant id; attacks without one hit the
    first enemy still standing."""

    action: Literal["attack", "defend", "flee"]
    target_id: int | None = None
