from __future__ import annotations

import re
from typing import Pattern

__all__ = []

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')


def parse_name_length_token(fmt: str) -> tuple[str, int]:
    if not (match := NAME_INT_RE.match(fmt)):
        raise ValueError(f"Can't parse 'name[length]' token '{fmt}'.")
    name, length_str = match.groups()
    return name, int(length_str) if length_str else 0

# A token name followed by a string that starts with '{' and ends with '}'
NAME_EXPRESSION_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)({.*})$')

def parse_name_expression_token(fmt: str) -> tuple[str, str]:
    if not (match := NAME_EXPRESSION_RE.match(fmt)):
        raise ValueError(f"Can't parse token '{fmt}'.")
    name, expression = match.groups()
    return name, expression