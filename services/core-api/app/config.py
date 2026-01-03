from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017/wish"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://localhost:5672/"
    jwt_secret: str = "dev-secret"
    jwt_issuer: str = "wish-with-me"
    access_token_ttl_days: int = 7
    refresh_token_ttl_days: int = 7


settings = Settings()
