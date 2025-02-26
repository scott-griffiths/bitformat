from __future__ import annotations
import sys
import ast
from typing import Any
from types import CodeType
import enum
from ._options import Options
import os
from lark import Lark
from enum import Enum


# Python 3.12 has these decorators built-in, but otherwise we mock them here.
if sys.version_info >= (3, 12):
    from typing import override, final
else:

    def override(f):
        return f

    def final(f):
        return f


class DtypeName(Enum):
    UINT = 'u'  # unsigned int
    INT = 'i'  # signed int
    BIN = 'bin'  # binary string
    OCT = 'oct'  # octal string
    HEX = 'hex'  # hexadecimal string
    BYTES = 'bytes'  # bytes object
    FLOAT = 'f'  # IEEE floating point
    BITS = 'bits'  # Bits object
    BOOL = 'bool'  # boolean
    PAD = 'pad'  # padding

    def __str__(self):
        return self.value


class Indenter:
    def __init__(self, indent_size: int | None = None, max_depth: int | None = None):
        """
        Create an Indenter object. The indent level is increased by using the object
        as a context manager.

        :param indent_size: The number of spaces to indent. If None, use the value of Options().indent_size.
        :type indent_size: int | None
        """
        if indent_size is None:
            indent_size = Options().indent_size
        self.indent_size = indent_size
        self.indent_level = 0
        self.max_depth = max_depth
        self.at_max_depth = False
        self.skipped_field_count = 0

    def __call__(self, s: str) -> str:
        """Indent the string and return it.
        Takes max_depth into account."""
        if self.max_depth is None or self.indent_level <= self.max_depth:
            self.at_max_depth = False
            skipped_str = ""
            if self.skipped_field_count > 0:
                skipped_str = (
                    " " * ((self.indent_level + 1) * self.indent_size)
                    + f"... ({self.skipped_field_count} fields)\n"
                )
                self.skipped_field_count = 0
            # Add a new line if part of a larger structure and it doesn't already have one.
            end = "\n" if self.indent_level > 0 and not s.endswith("\n") else ""
            return skipped_str + " " * (self.indent_level * self.indent_size) + s + end
        if not self.at_max_depth and self.indent_level == self.max_depth + 1:
            self.at_max_depth = True
            self.skipped_field_count += 1
            return ""
        if self.indent_level == self.max_depth + 1:
            self.skipped_field_count += 1
        return ""

    def __enter__(self):
        self.indent_level += 1
        return self

    def __exit__(self, type_, value, traceback):
        self.indent_level -= 1


class ExpressionError(ValueError):
    """Exception raised when failing to create or parse an Expression."""
    pass


class ANSIColours:
    """
    ANSI colour and style codes
    """
    # Reset all
    RESET = '\033[0m'

    # Regular Colours
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright/Light Colours
    BRIGHT_BLACK = '\033[90m'  # Gray
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Background Colours
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

    # Bright Background Colours
    BG_BRIGHT_BLACK = '\033[100m'
    BG_BRIGHT_RED = '\033[101m'
    BG_BRIGHT_GREEN = '\033[102m'
    BG_BRIGHT_YELLOW = '\033[103m'
    BG_BRIGHT_BLUE = '\033[104m'
    BG_BRIGHT_MAGENTA = '\033[105m'
    BG_BRIGHT_CYAN = '\033[106m'
    BG_BRIGHT_WHITE = '\033[107m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'  # Swap foreground/background colours
    HIDDEN = '\033[8m'
    STRIKE = '\033[9m'

    # Reset specific attributes
    RESET_BOLD = '\033[22m'
    RESET_DIM = '\033[22m'
    RESET_ITALIC = '\033[23m'
    RESET_UNDERLINE = '\033[24m'
    RESET_BLINK = '\033[25m'
    RESET_REVERSE = '\033[27m'
    RESET_HIDDEN = '\033[28m'
    RESET_STRIKE = '\033[29m'


class Colour:
    """A class to hold colour codes for terminal output. If use_colour is False, all codes are empty strings."""

    def __new__(cls, use_colour: bool) -> Colour:
        x = super().__new__(cls)
        cls.blue = ANSIColours.BLUE
        cls.green = ANSIColours.GREEN
        cls.red = ANSIColours.RED
        cls.magenta = ANSIColours.MAGENTA
        cls.orange = ANSIColours.BRIGHT_RED

        cls.off = ANSIColours.RESET
        cls.code = ANSIColours.YELLOW + ANSIColours.ITALIC
        cls.name = ANSIColours.GREEN + ANSIColours.ITALIC
        cls.dtype = ANSIColours.MAGENTA
        cls.value = ANSIColours.CYAN
        cls.const_value = ANSIColours.CYAN + ANSIColours.UNDERLINE

        if not use_colour:
            # Set all the above to ""
            for attr in dir(cls):
                if not attr.startswith("__") and isinstance(getattr(cls, attr), str):
                    setattr(cls, attr, "")
        return x


class Expression:
    """
    A compiled expression that can be evaluated with a dictionary of variables.

    Created with a string that starts and ends with braces, e.g. ``Expression('{x + 1}')``.

    Expressions are usually created when parsing fields such as :class:`Format` and :class:`If`, when
    an ``Expression`` will be implicitly created from sections between braces.

    .. code-block:: python

        e = Expression('{x + 1}')
        assert e.evaluate({'x': 5}) == 6

        f = Format('{x: u8, data: [u8; {x}]}')  # The number of items in data is an Expression.

    Only certain operations are permitted in an Expression - see the ``node_whitelist``. For security
    reasons, all builtins and double underscores are disallowed in the expression string.

    """

    def __init__(self, code_str: str):
        """Create an expression object from a string that starts and ends with braces."""
        code_str = code_str.strip()
        if len(code_str) < 2 or code_str[0] != "{" or code_str[-1] != "}":
            raise ExpressionError(
                f"Invalid Expression string: '{code_str}'. It should start with '{{' and end with '}}'."
            )
        # If the expression can be evaluated with no parameters then it's const and can be stored as such
        # Note that the const_value can be True, False, None, an int etc, so it's only valid if has_const_value is True.
        self.has_const_value = False
        self.const_value = None
        self.code_str = code_str[1:-1].strip()
        self.code = self._compile_safe_eval()
        try:
            self.const_value = self.evaluate()
            self.has_const_value = True
        except ExpressionError:
            pass

    """A whitelist of allowed AST nodes for the expression."""
    node_whitelist = {
        "BinOp",
        "Name",
        "Add",
        "Expr",
        "Mult",
        "FloorDiv",
        "Sub",
        "Load",
        "Module",
        "Constant",
        "UnaryOp",
        "USub",
        "Mod",
        "Pow",
        "BitAnd",
        "BitXor",
        "BitOr",
        "And",
        "Or",
        "BoolOp",
        "LShift",
        "RShift",
        "Eq",
        "NotEq",
        "Compare",
        "LtE",
        "GtE",
        "Subscript",
        "Gt",
        "Lt",
    }

    def _compile_safe_eval(self) -> CodeType:
        """Compile the expression, but only allow a whitelist of operations."""
        if "__" in self.code_str:
            raise ExpressionError(
                f"Invalid Expression '{self}'. Double underscores are not permitted."
            )
        try:
            nodes_used = set(
                [x.__class__.__name__ for x in ast.walk(ast.parse(self.code_str))]
            )
        except SyntaxError as e:
            raise ExpressionError(f"Failed to parse Expression '{self}': {e}")
        bad_nodes = nodes_used - Expression.node_whitelist
        if bad_nodes:
            raise ExpressionError(
                f"Disallowed operations used in Expression '{self}'. "
                f"Disallowed nodes were: {bad_nodes}. "
                f"If you think this operation should be allowed, please raise a bug report."
            )
        try:
            code = compile(self.code_str, "<string>", "eval")
        except SyntaxError as e:
            raise ExpressionError(f"Failed to compile Expression '{self}': {e}")
        return code

    def evaluate(self, kwargs: dict[str, Any] | None = None) -> Any:
        """Evaluate the expression, disallowing all builtins."""
        if self.has_const_value:
            return self.const_value
        try:
            value = eval(self.code, {"__builtins__": {}}, kwargs)
        except NameError as e:
            raise ExpressionError(f"Failed to evaluate Expression '{self}' with kwargs={kwargs}: {e}")
        return value

    def __str__(self) -> str:
        colour = Colour(not Options().no_color)
        if self.has_const_value:
            return str(self.const_value)
        return colour.code + "{" + self.code_str + "}" + colour.off

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{{{self.code_str}}}')"

    def __eq__(self, other) -> bool:
        if isinstance(other, Expression):
            return self.code_str == other.code_str
        if self.has_const_value and isinstance(self.const_value, int) and isinstance(other, int):
            return self.const_value == other
        return False

    def __hash__(self) -> int:
        return hash(self.code_str)


class Endianness(enum.Enum):
    BIG = "be"
    LITTLE = "le"
    NATIVE = "ne"
    UNSPECIFIED = ""


# The byte order of the system, used for the 'native' endianness modifiers ('_ne').
# If you'd like to emulate a different native endianness, you can set this to 'little' or 'big'.
byteorder: str = sys.byteorder


_lark_file_path = os.path.join(os.path.dirname(__file__), "format_parser.lark")
with open(_lark_file_path, "r") as f:
    parser_str = f.read()
    field_parser = Lark(parser_str, start='field_type', parser='earley')
