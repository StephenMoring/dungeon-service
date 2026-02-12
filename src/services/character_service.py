import json
from sqlmodel import Session
from src.models.character import Character, CharacterDescriptionCreate
from src.services.dm_agent import create_character


def create(
    character_description: CharacterDescriptionCreate, session: Session
) -> Character:
    character_json = create_character(character_description.description)
    if not character_json:
        raise ValueError("LLM did not return a response")
    try:
        character = json.loads(character_json)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid json")

    character["description"] = character_description.description
    new_character = Character(**character)
    with session:
        session.add(new_character)
        session.commit()
        session.refresh(new_character)
        print(new_character.model_dump_json)
        return new_character
