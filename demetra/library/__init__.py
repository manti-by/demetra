import re


MERGE_COMMAND_PATTERN = re.compile(r"@demetra-ai\b[\s,:.!-]*(?:please\s+)?merge\b", re.IGNORECASE)
REBASE_COMMAND_PATTERN = re.compile(r"@demetra-ai\b[\s,:.!-]*(?:please\s+)?rebase\b", re.IGNORECASE)
FIX_REVIEW_FINDINGS_COMMAND_PATTERN = re.compile(
    r"@demetra-ai\b[\s,:.!-]*(?:please\s+)?fix review findings\b", re.IGNORECASE
)

__all__ = ("FIX_REVIEW_FINDINGS_COMMAND_PATTERN", "MERGE_COMMAND_PATTERN", "REBASE_COMMAND_PATTERN")
