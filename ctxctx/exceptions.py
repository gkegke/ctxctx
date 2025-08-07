class CtxError(Exception):
    """Base exception for ctx package."""
    pass

class ConfigurationError(CtxError):
    """Raised when there's an issue with configuration loading or parsing."""
    pass

class GitError(CtxError):
    """Raised when a git command fails or git is not found."""
    pass

class FileReadError(CtxError):
    """Raised when a file cannot be read."""
    pass

class TooManyMatchesError(CtxError):
    """Raised when a query returns too many matches, exceeding configured limits."""
    def __init__(self, query: str, count: int, max_allowed: int, examples: list):
        self.query = query
        self.count = count
        self.max_allowed = max_allowed
        self.examples = examples
        super().__init__(
            f"Too many non-ignored matches for '{query}' ({count} found, max {max_allowed} allowed). "
            f"Please refine your query or increase MAX_MATCHES_PER_QUERY. "
            f"Examples: {', '.join(examples[:3])}{'...' if len(examples) > 3 else ''}"
        )