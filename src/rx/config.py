"""Settings from environment variables (prefix RX_ for the pipeline, SNOWFLAKE_ for the connection)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# CMS data API dataset ids (data.cms.gov/data.json), one per data year.
PRESCRIBER_DRUG_DATASETS = {
    2022: "b101b457-ffa4-49bb-8fd9-27c1266086e2",
    2023: "e54db557-cd82-4e91-a0fe-61aad5865d69",
    2024: "9552739e-3d05-4c1b-8eff-ecabf391e2e5",
}
SPENDING_BY_DRUG_DATASET = "7e0b4365-fd63-4a29-8f5e-e0ac9f66a81b"  # Part D Spending by Drug, data years 2020-2024
SPENDING_RELEASE_YEAR = 2024  # the release is one wide file; it loads as "year" 2024 and dbt unpivots 2020-2024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RX_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    exports_dir: Path = Path("bi/exports")
    state: str = Field(default="FL", pattern=r"^[A-Z]{2}$")
    years: str = "2022,2023,2024"

    def year_list(self) -> list[int]:
        return [int(y) for y in self.years.split(",") if y.strip()]


class SnowflakeSettings(BaseSettings):
    """Either a real account or the local emulator (host/port/protocol set, account `fakesnow`).

    On a real account the pipeline signs in with a key pair (SNOWFLAKE_PRIVATE_KEY_FILE): Snowflake does not allow
    password-only sign-in for service users, and infra/terraform creates the user with a public key only.
    """

    model_config = SettingsConfigDict(env_prefix="SNOWFLAKE_", env_file=".env", extra="ignore")

    account: str = "fakesnow"
    user: str = "fake"
    password: SecretStr = Field(default=SecretStr("snow"))
    private_key_file: Path | None = None
    role: str | None = None
    warehouse: str = "RX_WH"
    database: str = "RX"
    host: str | None = "127.0.0.1"
    port: int | None = 8085
    protocol: str | None = "http"

    @field_validator("database", "warehouse")
    @classmethod
    def _identifier(cls, value: str) -> str:
        # Interpolated into SQL as identifiers, so only plain unquoted Snowflake identifiers are accepted.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]{0,254}", value):
            raise ValueError(f"not a plain Snowflake identifier: {value!r}")
        return value

    @property
    def is_emulator(self) -> bool:
        return self.account == "fakesnow"

    def connect_kwargs(self) -> dict[str, object]:
        kw: dict[str, object] = {
            "account": self.account,
            "user": self.user,
            "warehouse": self.warehouse,
            "database": self.database,
            "session_parameters": {"QUERY_TAG": "medicare-rx-analytics"},
        }
        if self.private_key_file:
            kw.update(authenticator="SNOWFLAKE_JWT", private_key_file=str(self.private_key_file))
        else:
            kw["password"] = self.password.get_secret_value()
        if self.role:
            kw["role"] = self.role
        if self.is_emulator:
            kw.update(host=self.host, port=self.port, protocol=self.protocol, network_timeout=60)
        return kw


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_snowflake() -> SnowflakeSettings:
    return SnowflakeSettings()
