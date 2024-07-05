from __future__ import annotations
import os


class Options:
    """Internal class to create singleton module options instance."""

    _instance = None

    def __init__(self):
        self._bytealigned = False
        self.no_color = True
        # Turning off color for now
        # no_color = os.getenv('NO_COLOR')
        # self.no_color = True if no_color else False

    def __repr__(self) -> str:
        attributes = {attr: getattr(self, attr) for attr in dir(self) if not attr.startswith('_') and not callable(getattr(self, attr))}
        return '\n'.join(f"{attr}: {value!r}" for attr, value in attributes.items())

    @property
    def bytealigned(self) -> bool:
        return self._bytealigned

    @bytealigned.setter
    def bytealigned(self, value: bool) -> None:
        self._bytealigned = bool(value)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Options, cls).__new__(cls)
        return cls._instance
