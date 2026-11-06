import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt
from sqlmodel import Session, select, col
from src.config import SECRET_KEY
from src.models.campaign import Campaign
from src.models.character import (
    Character,
    CharacterCreate,
    CharacterDescriptionCreate,
    HeroClass,
    Race,
)
from src.models.message_history import MessageHistory
from src.models.user import User
from src.services.dm_agent import create_character
from src.services.combat_service import max_hp_for


# Character stats come from Claude, never from the player: a preview is signed for the
# player who asked for it, and saving accepts only an unaltered, unexpired preview.
PREVIEW_AUDIENCE = "character-preview"  # never valid as a session token, or vice versa
PREVIEW_LIFETIME = timedelta(hours=1)
STATS = (
    "strength",
    "perception",
    "endurance",
    "charisma",
    "intelligence",
    "agility",
    "luck",
)


class InvalidPreview(ValueError):
    """The preview token is missing, altered, expired or someone else's."""


def _within(value: object, low: int, high: int) -> int:
    number = value if isinstance(value, int) else low
    return min(high, max(low, number))


def create_preview(
    character_description: CharacterDescriptionCreate, user: User
) -> dict:
    """Generate a character sheet from the player's description, plus a token that
    lets this player save exactly that sheet within the hour."""
    stats_and_age_json = create_character(
        f"name: {character_description.name}, description: {character_description.description}, class: {character_description.hero_class}, race: {character_description.race}"
    )
    if not stats_and_age_json:
        raise ValueError("LLM did not return a response")
    try:
        generated = json.loads(stats_and_age_json)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")

    # The schema only says "integer": keep Claude's numbers on the scale the dice use.
    sheet = CharacterCreate(
        name=character_description.name,
        hero_class=character_description.hero_class,
        description=character_description.description,
        biography=str(generated.get("biography", ""))[:4000] or "Unknown.",
        age=_within(generated.get("age"), 1, 1000),
        **{stat: _within(generated.get(stat), 1, 10) for stat in STATS},
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "aud": PREVIEW_AUDIENCE,
            "exp": datetime.now(UTC) + PREVIEW_LIFETIME,
            "sheet": sheet.model_dump(),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    return {**sheet.model_dump(), "preview_token": token}


def create_from_preview(token: str, session: Session, user: User) -> Character:
    """Save the character a preview token was signed for, for the player it was
    signed for. Raises InvalidPreview otherwise."""
    assert user.id is not None
    try:
        claims = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"],
            audience=PREVIEW_AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise InvalidPreview("This character preview expired. Generate it again.")
    except jwt.InvalidTokenError:
        raise InvalidPreview("This character preview isn't valid. Generate it again.")
    if claims["sub"] != str(user.id):
        raise InvalidPreview("This character preview isn't valid. Generate it again.")

    sheet = CharacterCreate.model_validate(claims["sheet"])
    hp = max_hp_for(sheet.endurance)
    character = Character(
        **sheet.model_dump(), user_id=user.id, max_hp=hp, current_hp=hp
    )
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


def get_user_characters(session: Session, user: User):
    statement = (
        select(Character, Campaign)
        .outerjoin(Campaign, col(Character.campaign_id) == Campaign.id)
        .where(Character.user_id == user.id)
    )
    results = session.exec(statement).all()
    return [{"character": char, "campaign": campaign} for char, campaign in results]


def get_hero_classes(session: Session) -> Sequence[HeroClass]:
    return session.exec(select(HeroClass)).all()


def get_all_races(session: Session) -> Sequence[Race]:
    return session.exec(select(Race)).all()


def get_character_turns(
    character_id: int, session: Session
) -> Sequence[MessageHistory]:
    return session.exec(
        select(MessageHistory)
        .where(MessageHistory.character_id == character_id)
        .order_by(col(MessageHistory.created_at))
    ).all()
