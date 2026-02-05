import json
from sqlmodel import Session
from src.models.character import CharacterCreate, Character, CharacterDescriptionCreate
from src.services.dm_agent import create_character


def create(character_description: CharacterDescriptionCreate, session: Session):
    character = create_character(character_description.description)
    print(character)
    if character:
        character = json.loads(character)
        new_character = Character(**character)
        with session:
            session.add(new_character)
            session.commit()
            session.refresh(new_character)
            print(new_character.model_dump_json)
            return new_character
    else:
        return "Sorry could not create"
