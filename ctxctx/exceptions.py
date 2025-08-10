# ctxctx/exceptions.py
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
    """Raised when a query returns too many matches, exceeding configured
    limits.
    """

    def __init__(self, query: str, count: int, max_allowed: int, examples: list):
        self.query = query
        self.count = count
        self.max_allowed = max_allowed
        self.examples = examples
        super().__init__(
            f"Too many non-ignored matches for '{query}' ({count} found, "
            f"max {max_allowed} allowed). Please refine your query or "
            f"increase MAX_MATCHES_PER_QUERY. Examples: "
            f"{', '.join(examples[:3])}{'...' if len(examples) > 3 else ''}"
        )


class QueryProcessingError(CtxError):
    """Raised when an unexpected error occurs during file query processing."""

    def __init__(
        self,
        message: str = "An unexpected error occurred during query processing.",
        query: str = None,
    ):
        super().__init__(message)
        self.query = query


class OutputFormattingError(CtxError):
    """Raised when an unexpected error occurs during output content formatting."""

    def __init__(
        self,
        message: str = "An unexpected error occurred during output formatting.",
        file_path: str = None,
    ):
        super().__init__(message)
        self.file_path = file_path


class OutputWriteError(CtxError):
    """Raised when there's an error writing the final output files."""

    def __init__(self, message: str = "Error writing output file.", file_path: str = None):
        super().__init__(message)
        self.file_path = file_path
