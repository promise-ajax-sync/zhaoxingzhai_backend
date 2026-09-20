from app.models import Base


def test_core_database_metadata_contains_expected_tables_and_relationships() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "cases",
        "divination_records",
        "ai_interpretations",
        "refresh_tokens",
        "email_tokens",
    }
    records = Base.metadata.tables["divination_records"]
    interpretations = Base.metadata.tables["ai_interpretations"]
    refresh_tokens = Base.metadata.tables["refresh_tokens"]
    email_tokens = Base.metadata.tables["email_tokens"]

    assert {column.name for column in records.columns}.issuperset(
        {"user_id", "case_id", "question", "result_payload", "algorithm_version"}
    )
    assert {column.name for column in interpretations.columns}.issuperset(
        {"record_id", "content", "model_id", "prompt_version", "request_id"}
    )
    assert {foreign_key.target_fullname for foreign_key in records.foreign_keys} == {
        "users.id",
        "cases.id",
    }
    assert {foreign_key.target_fullname for foreign_key in interpretations.foreign_keys} == {
        "divination_records.id"
    }
    assert {foreign_key.target_fullname for foreign_key in refresh_tokens.foreign_keys} == {
        "users.id"
    }
    assert {foreign_key.target_fullname for foreign_key in email_tokens.foreign_keys} == {
        "users.id"
    }
