from __future__ import annotations
import os
import sys


def is_interactive() -> bool:
    return hasattr(sys, 'ps1')

class Options:
    """Internal class to create singleton module options instance."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Options, cls).__new__(cls)
            cls._bytealigned = False
            cls._verbose_bits_repr = is_interactive()
            no_color = os.getenv('NO_COLOR')
            cls.no_color = True if no_color else not is_interactive()
            # This is an experimental feature to use pure Python only (not bitarray)
            # It affects imports so you need to change its value here in the code.
            cls._use_pure_python = False
        return cls._instance


    def __init__(self):
        pass

    def __repr__(self) -> str:
        attributes = {attr: getattr(self, attr) for attr in dir(self) if not attr.startswith('_') and not callable(getattr(self, attr))}
        return '\n'.join(f"{attr}: {value!r}" for attr, value in attributes.items())

    @property
    def bytealigned(self) -> bool:
        return self._bytealigned

    @bytealigned.setter
    def bytealigned(self, value: bool) -> None:
        self._bytealigned = bool(value)

    @property
    def verbose_bits_repr(self) -> bool:
        return self._verbose_bits_repr

    @verbose_bits_repr.setter
    def verbose_bits_repr(self, value: bool) -> None:
        self._verbose_bits_repr = bool(value)

