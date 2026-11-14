"""Domain errors. The HTTP layer maps each to a problem response."""


class LedgerError(Exception):
    """Base class for expected, user-facing ledger errors."""


class ContentTooLarge(LedgerError):
    def __init__(self, size: int, limit: int) -> None:
        super().__init__(f"content is {size} bytes; the limit is {limit} bytes")
        self.size = size
        self.limit = limit


class RecordNotFound(LedgerError):
    pass


class VersionNotFound(LedgerError):
    pass


class ContentTampered(LedgerError):
    def __init__(self, content_hash: str) -> None:
        super().__init__(f"stored bytes no longer match content hash {content_hash}")
        self.content_hash = content_hash
