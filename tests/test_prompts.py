from src.services.prompts import master_system_prompt


def test_prompt_mentions_roll_check():
    assert "roll_check" in master_system_prompt


def test_prompt_drops_soft_rules():
    assert "not strict determiners" not in master_system_prompt
    assert "Story trumps mechanics" not in master_system_prompt
