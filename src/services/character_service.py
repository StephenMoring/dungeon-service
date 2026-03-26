import json
from sqlmodel import Session
from src.models.character import Character, CharacterDescriptionCreate
from src.models.user import User
from src.services.dm_agent import create_character


def create(character: Character, session: Session, user: User) -> Character:
    # character_json = create_character(character_description.description)
    # if not character_json:
    #     raise ValueError("LLM did not return a response")
    # try:
    #     character = json.loads(character_json)
    # except json.JSONDecodeError:
    #     raise ValueError("LLM returned invalid json")

    # character["description"] = character_description.description
    # with session:
    #     session.add(new_character)
    #     session.commit()
    #     session.refresh(new_character)
    #     return new_character

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
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")

    character = {}
    # character["description"] = character_description.description
    # character["name"] = character_description.name
    # character["hero_class"] = character_description.hero_class
    # character["race"] = character_description.race

    character["biography"] = stats_and_age.biography
    character["age"] = stats_and_age.age
    character["strength"] = stats_and_age.strength
    character["perception"] = stats_and_age.perception
    character["endurance"] = stats_and_age.endurance
    character["charisma"] = stats_and_age.charisma
    character["intelligence"] = stats_and_age.intelligence
    character["agility"] = stats_and_age.agility
    character["luck"] = stats_and_age.luck

    # to allow campaign_id to be null now and create after.
    # generate image too?

    return character
