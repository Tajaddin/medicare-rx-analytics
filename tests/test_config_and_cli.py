"""Settings validation and the CLI surface (no warehouse needed)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rx.cli import app
from rx.config import PRESCRIBER_DRUG_DATASETS, Settings, SnowflakeSettings

runner = CliRunner()


def test_emulator_connection_uses_host_and_port() -> None:
    kw = SnowflakeSettings().connect_kwargs()
    assert kw["account"] == "fakesnow"
    assert (kw["host"], kw["port"], kw["protocol"]) == ("127.0.0.1", 8085, "http")


def test_real_account_connection_has_no_emulator_host() -> None:
    kw = SnowflakeSettings(
        account="ab12345.us-east-1", user="RX_LOADER", password="x", role="RX_LOADER"
    ).connect_kwargs()
    assert not {"host", "port", "protocol"} & kw.keys()
    assert kw["role"] == "RX_LOADER"
    assert kw["session_parameters"] == {"QUERY_TAG": "medicare-rx-analytics"}


def test_key_pair_sign_in_sends_no_password(tmp_path) -> None:  # type: ignore[no-untyped-def]
    key = tmp_path / "rx.p8"
    kw = SnowflakeSettings(account="ab12345", user="RX_PIPELINE", private_key_file=key).connect_kwargs()
    assert kw["authenticator"] == "SNOWFLAKE_JWT"
    assert kw["private_key_file"] == str(key)
    assert "password" not in kw


@pytest.mark.parametrize("bad", ["RX; drop database RX", "rx-db", "1RX", ""])
def test_database_must_be_a_plain_identifier(bad: str) -> None:
    with pytest.raises(ValidationError):
        SnowflakeSettings(database=bad)


def test_password_is_not_printed() -> None:
    settings = SnowflakeSettings(password="s3cret-value")
    assert "s3cret-value" not in repr(settings)
    assert "s3cret-value" not in str(settings.model_dump())


def test_state_must_be_two_letters() -> None:
    with pytest.raises(ValidationError):
        Settings(state="Florida")


def test_year_list() -> None:
    assert Settings(years="2022, 2024,").year_list() == [2022, 2024]


def test_plan_lists_every_dataset_year(monkeypatch: pytest.MonkeyPatch) -> None:
    from rx import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("RX_YEARS", "2023,2024")
    result = runner.invoke(app, ["plan"])
    config.get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    lines = [line.split("\t") for line in result.output.strip().splitlines()]
    assert lines == [
        ["prescriber_drug", "2023", PRESCRIBER_DRUG_DATASETS[2023], "FL"],
        ["prescriber_drug", "2024", PRESCRIBER_DRUG_DATASETS[2024], "FL"],
        ["spending_by_drug", "2024", "7e0b4365-fd63-4a29-8f5e-e0ac9f66a81b", "-"],
    ]


def test_plan_refuses_a_year_without_a_dataset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from rx import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("RX_YEARS", "2019")
    result = runner.invoke(app, ["plan"])
    config.get_settings.cache_clear()
    assert result.exit_code != 0


def test_load_rejects_an_unknown_dataset(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["load", "--dataset", "bogus", "--year", "2024", "--pages", str(tmp_path)])
    assert result.exit_code == 2


def test_load_rejects_a_missing_folder(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(
        app, ["load", "--dataset", "prescriber_drug", "--year", "2024", "--pages", str(tmp_path / "x")]
    )
    assert result.exit_code == 2
