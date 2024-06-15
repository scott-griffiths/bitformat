from __future__ import annotations

import functools
import re
from typing import Pattern

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')

CACHE_SIZE = 256

MULTIPLICATIVE_RE: Pattern[str] = re.compile(r'^(?P<factor>.*)\*(?P<token>.+)')

# Hex, oct or binary literals
LITERAL_RE: Pattern[str] = re.compile(r'^(?P<name>0([xob]))(?P<value>.+)', re.IGNORECASE)


@functools.lru_cache(CACHE_SIZE)
def parse_name_length_token(fmt: str, **kwargs) -> tuple[str, int | None]:
    # Any single token with just a name and length
    if m2 := NAME_INT_RE.match(fmt):
        name = m2.group(1)
        length_str = m2.group(2)
        length = None if length_str == '' else int(length_str)
    else:
        raise ValueError(f"Can't parse 'name[length]' token '{fmt}'.")
    return name, length


@functools.lru_cache(CACHE_SIZE)
def parse_single_token(token: str) -> tuple[str, int | None, str | None]:
    if (equals_pos := token.find('=')) == -1:
        value = None
    else:
        value = token[equals_pos + 1:]
        token = token[:equals_pos]
    if m2 := NAME_INT_RE.match(token):
        name = m2.group(1)
        length_str = m2.group(2)
        if length_str == '':
            return name, None, value
        return name, int(length_str), value
    else:
        raise ValueError(f"Can't parse token '{token}'. It should be in the form 'name[length][=value]'.")


@functools.lru_cache(CACHE_SIZE)
def preprocess_tokens(fmt: str) -> list[str]:
    # Remove whitespace
    fmt = ''.join(fmt.split())
    meta_tokens = fmt.split(',')
    final_tokens = []

    for meta_token in meta_tokens:
        if meta_token == '':
            continue
        # Extract factor and actual token if a multiplicative factor exists
        factor = 1
        if m := MULTIPLICATIVE_RE.match(meta_token):
            factor = int(m.group('factor'))
            meta_token = m.group('token')

        tokens = [meta_token]

        # Extend final tokens list with parsed tokens, repeated by the factor
        final_tokens.extend(tokens * factor)
    return final_tokens


@functools.lru_cache(CACHE_SIZE)
def tokenparser(fmt: str) -> \
        list[tuple[str, int | str | None, str | None]]:
    """Divide the format string into tokens and parse them.

    Return list of [initialiser, length, value]
    initialiser is one of: hex, oct, bin, uint, int, 0x, 0o, 0b etc.
    length is None if not known, as is value.

    tokens must be of the form: [factor*][initialiser][length][=value]

    """
    tokens = preprocess_tokens(fmt)
    ret_vals: list[tuple[str, str | int | None, str | None]] = []
    for token in tokens:
        if token == '':
            continue
        # Match literal tokens of the form 0x... 0o... and 0b...
        if m := LITERAL_RE.match(token):
            ret_vals.append((m.group('name'), None, m.group('value')))
            continue
        name, length, value = parse_single_token(token)
        ret_vals.append((name, length, value))
    return ret_vals
