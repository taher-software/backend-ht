from pydantic import EmailStr, HttpUrl, Field
from functools import lru_cache
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    mail_username: EmailStr = Field(
        env="mail_username", default="ttaherhagui@gmail.com"
    )
    mail_pwd: str = Field(env="mail_pwd", default="jqlq vczg qgtj kobj")
    application_url: HttpUrl = Field(
        env="application_url", default="http://localhost:3000/"
    )
    jwt_access_expires: int = 14400
    jwt_algorithm: str = Field(env="jwt_algorithm", default="HS256")
    db_url: str = Field(
        env="db_url", default="postgresql://haggui:77471580t@localhost/bodor_db"
    )
    jwt_secret: str = Field(env="jwt_secret", default="taher")
    openia_apikey: str = Field(
        env="openia_apikey",
        default="",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
os.environ["OPENAI_API_KEY"] = settings.openia_apikey
