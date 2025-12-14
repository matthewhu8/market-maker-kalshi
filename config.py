import os
from pydantic import Field
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # API Configuration
    API_BASE_URL: str = Field(default="https://api.elections.kalshi.com/trade-api/v2", validation_alias="KALSHI_API_URL")
    WS_Url: str = Field(default="wss://api.elections.kalshi.com/trade-api/ws/v2", validation_alias="KALSHI_WS_URL")
    
    # Credentials
    KEY_ID: str = Field(..., validation_alias="API_KEY")
    PRIVATE_KEY_PATH: str = Field(default="rsa_private_key.txt", validation_alias="PRIVATE_KEY")
    
    # Trading Configuration
    TARGET_TICKER: str = Field(default="KXELONMARS-99", validation_alias="TARGET_TICKER") 
    SPREAD_CENTS: int = Field(default=2, validation_alias="SPREAD_CENTS")
    ORDER_SIZE: int = Field(default=2, validation_alias="ORDER_SIZE")

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = "ignore" 

def load_config() -> Config:
    return Config()
