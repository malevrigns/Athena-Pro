class LLMSettings(BaseSettings):
    model: str = "gpt-4o-mini"
    
    class Config:
        env_prefix = "LLM_"
        env_file = ".env"