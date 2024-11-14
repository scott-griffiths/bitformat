import re
from typing import Pattern

__all__ = []

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$")


def parse_name_size_token(fmt: str) -> tuple[str, int]:
    if not (match := NAME_INT_RE.match(fmt)):
        raise ValueError(f"Can't parse token '{fmt}' as 'name[length]'.")
    name, length_str = match.groups()
    return name, int(length_str) if length_str else 0


def parse_name_to_name_and_modifier(name: str) -> tuple[str, str]:
    modifiers = name.split("_")
    if len(modifiers) == 1:
        return name, ""
    if len(modifiers) == 2:
        return modifiers[0], modifiers[1]
    raise ValueError(f"Can't parse name '{name}' as more than one '_' is present.")


# A token name followed by a string that starts with '{' and ends with '}'
NAME_EXPRESSION_RE: Pattern[str] = re.compile(r"^([a-zA-Z][a-zA-Z0-9_]*?)({.*})$")


def parse_name_expression_token(fmt: str) -> tuple[str, str]:
    if not (match := NAME_EXPRESSION_RE.match(fmt)):
        raise ValueError(f"Can't parse token '{fmt}'.")
    name, expression = match.groups()
    return name, expression
