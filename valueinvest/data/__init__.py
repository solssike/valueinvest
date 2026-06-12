from .fetcher import (
    BaseFetcher,
    FetchResult,
    HistoryResult,
    detect_source,
    get_fetcher,
    normalize_ashare_ticker,
)
from .patch import (
    EarningsPatch,
    PatchResult,
    QuarterlyEarnings,
    apply_earnings_patch,
    load_patch_from_json,
)

__all__ = [
    "BaseFetcher",
    "FetchResult",
    "HistoryResult",
    "detect_source",
    "get_fetcher",
    "normalize_ashare_ticker",
    "EarningsPatch",
    "PatchResult",
    "QuarterlyEarnings",
    "apply_earnings_patch",
    "load_patch_from_json",
]
