from __future__ import annotations
import sys
import ast
from typing import Any
import enum
from ._options import Options
import os
from lark import Lark


# Python 3.12 has these decorators built-in, but otherwise we mock them here.
if sys.version_info >= (3, 12):
    from typing import override, final
else:

    def override(f):
        return f

    def final(f):
        return f


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


class Colour:
    """A class to hold colour codes for terminal output. If use_colour is False, all codes are empty strings."""

    def __new__(cls, use_colour: bool) -> Colour:
        x = super().__new__(cls)
        if use_colour:
            cls.blue = "\033[34m"
            cls.purple = "\033[35m"
            cls.green = "\033[32m"
            cls.red = "\033[31m"
            cls.cyan = "\033[36m"
            cls.off = "\033[0m"
        else:
            cls.blue = cls.purple = cls.green = cls.red = cls.cyan = cls.off = ""
        return x


class Expression:
    """
    A compiled expression that can be evaluated with a dictionary of variables.

    Created with a string that starts and ends with braces, e.g. '{x + 1}'.
    """

    def __init__(self, code_str: str):
        """Create an expression object from a string that starts and ends with braces."""
        code_str = code_str.strip()
        if len(code_str) < 2 or code_str[0] != "{" or code_str[-1] != "}":
            raise ExpressionError(
                f"Invalid Expression string: '{code_str}'. It should start with '{{' and end with '}}'."
            )
        self.code_str = code_str[1:-1].strip()
        self.code = self._compile_safe_eval()

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

    def _compile_safe_eval(self):
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
        try:
            value = eval(self.code, {"__builtins__": {}}, kwargs)
        except NameError as e:
            raise ExpressionError(
                f"Failed to evaluate Expression '{self}' with kwargs={kwargs}: {e}"
            )
        return value

    def __str__(self):
        return f"{{{self.code_str}}}"

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.__str__()}')"

    def __eq__(self, other):
        if isinstance(other, Expression):
            return self.code_str == other.code_str
        return False


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
    lark_parser = Lark(f, start=["format", "field"])
