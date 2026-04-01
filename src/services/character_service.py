import json
from collections.abc import Sequence
from sqlmodel import Session, select, col
from src.models.campaign import Campaign
from src.models.character import Character, CharacterDescriptionCreate, HeroClass, Race
from src.models.message_history import MessageHistory
from src.models.user import User
from src.services.dm_agent import create_character


def create(character: Character, session: Session, user: User) -> Character:
    assert user.id is not None
    character.user_id = user.id
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


def create_preview(character_description: CharacterDescriptionCreate) -> dict:
    stats_and_age_json = create_character(
        f"name: {character_description.name}, description: {character_description.description}, class: {character_description.hero_class}, race: {character_description.race}"
    )
    if not stats_and_age_json:
        raise ValueError("LLM did not return a response")
    try:
        stats_and_age = json.loads(stats_and_age_json)
        return stats_and_age
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")


def get_user_characters(session: Session, user: User):
    print("fetching user's characters from db")
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


def get_character_turns(character_id: int, session: Session) -> Sequence[MessageHistory]:
    return session.exec(
        select(MessageHistory)
        .where(MessageHistory.character_id == character_id)
        .order_by(col(MessageHistory.created_at))
    ).all()
