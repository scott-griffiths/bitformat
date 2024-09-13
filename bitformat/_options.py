from __future__ import annotations
import os
import sys


def is_interactive() -> bool:
    return hasattr(sys, 'ps1')

class Options:
    """Returns the singleton module options instance.

    To query and change module options create an instance and set or get properties of it.

    .. code-block:: python

        if Options().bytealigned:
            # ...
            Options().bytealigned = False

    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Options, cls).__new__(cls)
            cls._bytealigned = False
            cls._verbose_bits_repr = is_interactive()
            no_color = os.getenv('NO_COLOR')
            cls._no_color = True if no_color else not is_interactive()
            # This is an experimental feature to use pure Python only (not bitarray)
            # It affects imports so you need to change its value here in the code.
            cls._use_pure_python = False
        return cls._instance

    def __init__(self):
        pass

    def __setattr__(self, name, value):
        if hasattr(self, name):
            super().__setattr__(name, value)
        else:
            raise AttributeError(f"Cannot add new attribute '{name}' to Options. "
                                 f"Only existing attributes can be modified:\n{self!r}")

    def __repr__(self) -> str:
        attributes = {attr: getattr(self, attr) for attr in dir(self) if not attr.startswith('_') and not callable(getattr(self, attr))}
        return '\n'.join(f"{attr}: {value!r}" for attr, value in attributes.items())

    @property
    def bytealigned(self) -> bool:
        """Governs the default byte alignment option in methods that use it."""
        return self._bytealigned

    @bytealigned.setter
    def bytealigned(self, value: bool) -> None:
        self._bytealigned = bool(value)

    @property
    def verbose_bits_repr(self) -> bool:
        """If True then Bits objects will be given a more verbose output when printed in interactive mode."""
        return self._verbose_bits_repr

    @verbose_bits_repr.setter
    def verbose_bits_repr(self, value: bool) -> None:
        self._verbose_bits_repr = bool(value)

    @property
    def no_color(self) -> bool:
        """If True then no ANSI color codes will be used in output."""
        return self._no_color

    @no_color.setter
    def no_color(self, value: bool) -> None:
        self._no_color = bool(value)
