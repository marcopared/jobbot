from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobbot"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/jobbot"
    redis_url: str = "redis://localhost:6379/0"
    artifact_dir: str = "./storage/artifacts"
    profile_dir: str = "./storage/profiles"
    ui_base_url: str = "http://localhost:5173"
    default_search_query: str = "backend engineer fintech"
    default_location: str = "New York, NY"
    scrape_hours_old: int = 48
    scrape_results_wanted: int = 50
    jobspy_enabled: bool = True
    wellfound_enabled: bool = False
    builtinnyc_enabled: bool = False
    yc_enabled: bool = False
    apollo_api_key: str = ""
    scrapeops_api_key: str = ""
    push_provider: str = "pushover"
    pushover_token: str = ""
    pushover_user: str = ""
    ntfy_topic_url: str = ""
    base_resume_path: str = "./storage/base_resume.pdf"
    master_skills_path: str = "./storage/master_skills.json"
    resume_tailor_enabled: bool = True
    playwright_headful: bool = True
    playwright_slow_mo_ms: int = 0
    playwright_profile_name: str = "default"
    playwright_timeout_ms: int = 30000
    log_level: str = "DEBUG"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
