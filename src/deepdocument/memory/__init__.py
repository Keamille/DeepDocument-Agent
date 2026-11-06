"""记忆层：提示预算与全局画像。"""

from deepdocument.memory.budget import (
    BUDGET,
    EXCERPT_PER_SOURCE,
    MAX_OUTPUT_TOKENS,
    MIN_CONTEXT_TOKENS,
    PROMPT_TOKEN_BUDGET,
    build_prompt,
    estimate_tokens,
    truncate_to_budget,
)
from deepdocument.memory.profile import (
    load_profile,
    profile_to_prompt,
    save_profile,
    update_profile,
)
from deepdocument.memory.snapshots import (
    capture_file_snapshots,
    detect_external_changes,
)

__all__ = [
    "BUDGET",
    "EXCERPT_PER_SOURCE",
    "MAX_OUTPUT_TOKENS",
    "MIN_CONTEXT_TOKENS",
    "PROMPT_TOKEN_BUDGET",
    "build_prompt",
    "capture_file_snapshots",
    "detect_external_changes",
    "estimate_tokens",
    "load_profile",
    "profile_to_prompt",
    "save_profile",
    "truncate_to_budget",
    "update_profile",
]
