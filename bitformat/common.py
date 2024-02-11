from __future__ import annotations
import sys
import ast
from typing import Any

indent_size = 4

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
    def __init__(self, code_str: str):
        """Create an expression object from a string that starts and ends with braces."""
        code_str = code_str.strip()
        if code_str[0] != '{' or code_str[-1] != '}':
            raise ValueError(f"Invalid expression: '{code_str}'. It should start with '{{' and end with '}}'.")
        self.code_str = code_str[1:-1].strip()
        self.code = self.compile_safe_eval()
        # When the expression is evaluated the value is stored.
        self.value = None

    def compile_safe_eval(self):
        """Compile the expression, but only allow a whitelist of operations."""
        node_whitelist = {'BinOp', 'Name', 'Add', 'Expr', 'Mult', 'FloorDiv', 'Sub', 'Load', 'Module', 'Constant',
                          'UnaryOp', 'USub', 'Mod', 'Pow', 'BitAnd', 'BitXor', 'BitOr', 'And', 'Or', 'BoolOp', 'LShift',
                          'RShift', 'Eq', 'NotEq', 'Compare', 'LtE', 'GtE', 'Subscript'}
        nodes_used = set([x.__class__.__name__ for x in ast.walk(ast.parse(self.code_str))])
        bad_nodes = nodes_used - node_whitelist
        if bad_nodes:
            raise SyntaxError(f"bitformat.Expression: Disallowed operations used in expression '{self.code_str}'. "
                              f"Disallowed nodes were: {bad_nodes}. "
                              f"If you think this operation should be allowed, please raise bug report.")
        if '__' in self.code_str:
            raise SyntaxError(f"bitformat.Expression: Invalid expression '{self.code_str}'. Double underscores are not permitted.")
        code = compile(self.code_str, "<string>", "eval")
        return code

    def safe_eval(self, vars_: dict[str, Any]) -> Any:
        """Evaluate the expression, disallowing all builtins."""
        self.value = eval(self.code, {"__builtins__": {}}, vars_)
        return self.value

    def clear(self):
        self.value = None

    def __str__(self):
        value_str = '' if self.value is None else f' = {self.value}'
        return f'{{{self.code_str}{value_str}}}'
