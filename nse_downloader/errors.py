class DownloadError(RuntimeError):
    """An NSE response could not be safely used."""


class ValidationError(ValueError):
    """Downloaded records did not meet the configured data contract."""


class AccessBlockedError(DownloadError):
    """NSE denied a public request; no evasion is attempted."""


class InvalidResponseError(DownloadError):
    """A response could not be interpreted as configured JSON."""
