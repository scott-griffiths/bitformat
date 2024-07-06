
class Error(Exception):
    """Base class for errors in the bitformat module."""

    def __init__(self, *params: object) -> None:
        self.msg = params[0] if params else ''
        self.params = params[1:]


class ReadError(Error, IndexError):
    """Reading or peeking past the end of a Bits."""


class ByteAlignError(Error):
    """Whole-byte position or length needed."""

