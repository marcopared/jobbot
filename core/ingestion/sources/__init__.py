from core.ingestion.sources.auth_boards import (
    BaseAuthBoardSourceAdapter,
    LinkedInJobsSourceAdapter,
    WellfoundSourceAdapter,
    YCJobsSourceAdapter,
)
from core.ingestion.sources.base import SourceAdapter
from core.ingestion.sources.public_boards import (
    BasePublicBoardSourceAdapter,
    BuiltInNYCSourceAdapter,
    StartupJobsNYCSourceAdapter,
    UnsupportedPublicBoardSourceAdapter,
    WelcomeToTheJungleSourceAdapter,
)

__all__ = [
    "BaseAuthBoardSourceAdapter",
    "BasePublicBoardSourceAdapter",
    "BuiltInNYCSourceAdapter",
    "LinkedInJobsSourceAdapter",
    "SourceAdapter",
    "StartupJobsNYCSourceAdapter",
    "UnsupportedPublicBoardSourceAdapter",
    "WelcomeToTheJungleSourceAdapter",
    "WellfoundSourceAdapter",
    "YCJobsSourceAdapter",
]
