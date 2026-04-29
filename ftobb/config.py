from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Settings(BaseSettings):
    endpoint: str = Field(default="")
    access_key: str = Field(default="")
    secret_key: str = Field(default="")
    bucket: str = Field(default="")
    region: str | None = Field(default=None)
    secure: bool = Field(default=True)
    get_url_expiry_seconds: int = Field(
        default=3600  # One hour
    )


class BotSettings(BaseSettings):
    allowed_user_ids: list[int] = Field(default=[])
    base_url: str | None = Field(default=None)
    token: str = Field(default="")


class ApplicationSetting(BaseSettings):
    bot: BotSettings = Field(default=BotSettings())
    s3: S3Settings = Field(default=S3Settings())

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_prefix="P2I_",
        env_nested_delimiter=".",
    )


settings = ApplicationSetting()
