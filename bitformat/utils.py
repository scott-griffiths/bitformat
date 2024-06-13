from __future__ import annotations

import functools
import re
from typing import Tuple, List, Pattern, Union

# A token name followed by an integer number
NAME_INT_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?)(\d*)$')

# A token name followed by : then an arbitrary keyword
NAME_KWARG_RE: Pattern[str] = re.compile(r'^([a-zA-Z][a-zA-Z0-9_]*?):([a-zA-Z0-9_]+)$')

CACHE_SIZE = 256

MULTIPLICATIVE_RE: Pattern[str] = re.compile(r'^(?P<factor>.*)\*(?P<token>.+)')

# Hex, oct or binary literals
LITERAL_RE: Pattern[str] = re.compile(r'^(?P<name>0([xob]))(?P<value>.+)', re.IGNORECASE)


@functools.lru_cache(CACHE_SIZE)
def parse_name_length_token(fmt: str, **kwargs) -> Tuple[str, int | None]:
    # Any single token with just a name and length
    if m2 := NAME_INT_RE.match(fmt):
        name = m2.group(1)
        length_str = m2.group(2)
        length = None if length_str == '' else int(length_str)
    else:
        # Maybe the length is in the kwargs?
        if m := NAME_KWARG_RE.match(fmt):
            name = m.group(1)
            try:
                length_str = kwargs[m.group(2)]
            except KeyError:
                raise ValueError(f"Can't parse 'name[length]' token '{fmt}'.")
            length = int(length_str)
        else:
            raise ValueError(f"Can't parse 'name[length]' token '{fmt}'.")
    return name, length


@functools.lru_cache(CACHE_SIZE)
def parse_single_token(token: str) -> Tuple[str, str, str | None]:
    if (equals_pos := token.find('=')) == -1:
        value = None
    else:
        value = token[equals_pos + 1:]
        token = token[:equals_pos]

    if m2 := NAME_INT_RE.match(token):
        name = m2.group(1)
        length_str = m2.group(2)
        length = None if length_str == '' else length_str
    elif m3 := NAME_KWARG_RE.match(token):
        # name then a keyword for a length
        name = m3.group(1)
        length = m3.group(2)
    else:
        # If you don't specify a 'name' then the default is 'bits'
        name = 'bits'
        length = token
    return name, length, value


@functools.lru_cache(CACHE_SIZE)
def preprocess_tokens(fmt: str) -> List[str]:
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
def tokenparser(fmt: str, keys: Tuple[str, ...] = ()) -> \
        Tuple[bool, List[Tuple[str, Union[int, str, None], str | None]]]:
    """Divide the format string into tokens and parse them.

    Return stretchy token and list of [initialiser, length, value]
    initialiser is one of: hex, oct, bin, uint, int, se, ue, 0x, 0o, 0b etc.
    length is None if not known, as is value.

    If the token is in the keyword dictionary (keys) then it counts as a
    special case and isn't messed with.

    tokens must be of the form: [factor*][initialiser][:][length][=value]

    """
    tokens = preprocess_tokens(fmt)
    stretchy_token = False
    ret_vals: List[Tuple[str, Union[str, int, None], str | None]] = []
    for token in tokens:
        if keys and token in keys:
            # Don't bother parsing it, it's a keyword argument
            ret_vals.append((token, None, None))
            continue
        if token == '':
            continue
        # Match literal tokens of the form 0x... 0o... and 0b...
        if m := LITERAL_RE.match(token):
            ret_vals.append((m.group('name'), None, m.group('value')))
            continue
        name, length, value = parse_single_token(token)
        if length is None:
            stretchy_token = True
        if length is not None:
            # Try converting length to int, otherwise check it's a key.
            try:
                length = int(length)
            except ValueError:
                if not keys or length not in keys:
                    raise ValueError(f"Don't understand length '{length}' of token.")
        ret_vals.append((name, length, value))
    return stretchy_token, ret_vals
