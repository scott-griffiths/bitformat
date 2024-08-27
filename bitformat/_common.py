from __future__ import annotations
import sys
import ast
from typing import Any
import enum

indent_size = 4

# Python 3.12 has these decorators built-in, but otherwise we mock them here.
if sys.version_info >= (3, 12):
    from typing import override, final
else:
    def override(f): return f
    def final(f): return f


def _indent(level: int) -> str:
    return ' ' * (level * indent_size)


class Colour:
    """A class to hold colour codes for terminal output. If use_colour is False, all codes are empty strings."""
    def __new__(cls, use_colour: bool) -> Colour:
        x = super().__new__(cls)
        if use_colour:
            cls.blue = '\033[34m'
            cls.purple = '\033[35m'
            cls.green = '\033[32m'
            cls.red = '\033[31m'
            cls.cyan = '\033[36m'
            cls.off = '\033[0m'
        else:
            cls.blue = cls.purple = cls.green = cls.red = cls.cyan = cls.off = ''
        return x


is_interactive_shell = hasattr(sys, 'ps1')
colour = Colour(is_interactive_shell)


class Expression:
    """
    A compiled expression that can be evaluated with a dictionary of variables.

    Created with a string that starts and ends with braces, e.g. '{x + 1}'.
    """
    def __init__(self, code_str: str):
        """Create an expression object from a string that starts and ends with braces."""
        code_str = code_str.strip()
        if len(code_str) < 2 or code_str[0] != '{' or code_str[-1] != '}':
            raise ValueError(f"Invalid Expression string: '{code_str}'. It should start with '{{' and end with '}}'.")
        self.code_str = code_str[1:-1].strip()
        self.code = self._compile_safe_eval()

    node_whitelist = {'BinOp', 'Name', 'Add', 'Expr', 'Mult', 'FloorDiv', 'Sub', 'Load', 'Module', 'Constant',
                      'UnaryOp', 'USub', 'Mod', 'Pow', 'BitAnd', 'BitXor', 'BitOr', 'And', 'Or', 'BoolOp', 'LShift',
                      'RShift', 'Eq', 'NotEq', 'Compare', 'LtE', 'GtE', 'Subscript'}

    def _compile_safe_eval(self):
        """Compile the expression, but only allow a whitelist of operations."""
        if '__' in self.code_str:
            raise ValueError(f"Invalid Expression '{self}'. Double underscores are not permitted.")
        try:
            nodes_used = set([x.__class__.__name__ for x in ast.walk(ast.parse(self.code_str))])
        except SyntaxError as e:
            raise ValueError(f"Failed to parse Expression '{self}': {e}")
        bad_nodes = nodes_used - Expression.node_whitelist
        if bad_nodes:
            raise ValueError(f"Disallowed operations used in Expression '{self}'. "
                             f"Disallowed nodes were: {bad_nodes}. "
                             f"If you think this operation should be allowed, please raise a bug report.")
        try:
            code = compile(self.code_str, "<string>", "eval")
        except SyntaxError as e:
            raise ValueError(f"Failed to compile Expression '{self}': {e}")
        return code

    def evaluate(self, **kwargs) -> Any:
        """Evaluate the expression, disallowing all builtins."""
        try:
            value = eval(self.code, {"__builtins__": {}}, kwargs)
        except NameError as e:
            raise ValueError(f"Failed to evaluate Expression '{self}' with kwargs={kwargs}: {e}")
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
    BIG = 'be'
    LITTLE = 'le'
    NATIVE = 'ne'
    UNSPECIFIED = ''
