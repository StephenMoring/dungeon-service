from sqlmodel import Session
from src.models.character import CharacterCreate, Character


def create(character: CharacterCreate, session: Session):
    new_character = Character(**character.model_dump())
    with session:
        session.add(new_character)
        session.commit()
        session.refresh(new_character)
        print(new_character.model_dump_json)
        return new_character
