from pathlib import Path

from innobrain.config.loader import load_env_file


def test_load_env_file_missing_file_returns_empty() -> None:
    loaded = load_env_file(Path("/nonexistent/.env"))
    assert loaded == ()


def test_load_env_file_parses_valid_lines_and_ignores_blanks_and_comments(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        # This is a comment line

        VALID_KEY_1=first_value
        # Another comment
        VALID_KEY_2="quoted value with spaces"
        VALID_KEY_3='single quoted'
        MALFORMED_LINE_WITHOUT_EQUALS
        =MISSING_KEY
        VALID_KEY_4=value_with=extra=equals
        """,
        encoding="utf-8",
    )

    custom_env: dict[str, str] = {}
    loaded = load_env_file(env_file, target_env=custom_env)

    assert set(loaded) == {"VALID_KEY_1", "VALID_KEY_2", "VALID_KEY_3", "VALID_KEY_4"}
    assert custom_env["VALID_KEY_1"] == "first_value"
    assert custom_env["VALID_KEY_2"] == "quoted value with spaces"
    assert custom_env["VALID_KEY_3"] == "single quoted"
    assert custom_env["VALID_KEY_4"] == "value_with=extra=equals"
    assert "MALFORMED_LINE_WITHOUT_EQUALS" not in custom_env


def test_load_env_file_preserves_existing_environment_precedence(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        EXISTING_KEY=new_file_value
        NEW_KEY=file_value
        """,
        encoding="utf-8",
    )

    custom_env = {"EXISTING_KEY": "prior_process_value"}
    loaded = load_env_file(env_file, target_env=custom_env)

    # EXISTING_KEY is NOT overwritten
    assert custom_env["EXISTING_KEY"] == "prior_process_value"
    assert custom_env["NEW_KEY"] == "file_value"
    # Loaded returns only keys that were newly set
    assert loaded == ("NEW_KEY",)


def test_load_env_file_never_returns_secret_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    secret_value = "super_secret_token_12345"
    env_file.write_text(f"API_SECRET={secret_value}\n", encoding="utf-8")

    custom_env: dict[str, str] = {}
    loaded = load_env_file(env_file, target_env=custom_env)

    # Return value must contain only variable names, never secret values
    assert secret_value not in loaded
    assert loaded == ("API_SECRET",)


def test_load_env_file_rejects_export_invalid_and_path_like_keys(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "export VALID_EXPORT=ignored\n"
        "GOOD_NAME=accepted\n"
        "BAD-NAME=ignored\n"
        "BAD NAME=ignored\n"
        "9START=ignored\n"
        "C:\\path=ignored\n",
        encoding="utf-8",
    )
    custom_env: dict[str, str] = {}

    loaded = load_env_file(env_file, target_env=custom_env)

    assert loaded == ("GOOD_NAME",)
    assert custom_env == {"GOOD_NAME": "accepted"}
