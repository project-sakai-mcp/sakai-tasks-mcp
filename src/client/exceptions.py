"""Exceptions for Sakai client communication."""


class SakaiTimeoutError(Exception):
    """Raised when an HTTP request to Sakai LMS times out."""

    def __init__(
        self,
        message: str,
        timeout: float | None = None,
        failed_sites: list[str] | None = None,
    ):
        super().__init__(message)
        self.timeout = timeout
        self.failed_sites = failed_sites or []
