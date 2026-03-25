"""
Parser for Paradox PDXScript text format.

Uses regex-based tokenization for performance (C-speed), then builds
the tree in a single pass.

Handles:
- key = value pairs
- key = { ... } nested blocks
- Arrays (lists of values inside { })
- Quoted and unquoted strings
- Numbers (int and float)
- Dates like 1836.1.1
- yes/no booleans
- Duplicate keys (stored as lists)
- Operators: = > < >= <=
"""
import re
import sys
from typing import Any

# Increase recursion limit for deeply nested save files
sys.setrecursionlimit(15000)

# Single regex that tokenizes all PDX elements.
# Ordering matters: comments and quoted strings must match before operators/tokens.
_TOKEN_RE = re.compile(r"""
    \#[^\n]*             |  # comment — skip entirely
    ("(?:[^"\\]|\\.)*")  |  # quoted string (group 1)
    ([{}])               |  # braces (group 2)
    ([=><]=?)            |  # operators (group 3)
    ([^\s={}><\#"]+)        # unquoted token (group 4)
""", re.VERBOSE)


def _convert(token: str) -> Any:
    """Convert an unquoted string token to the appropriate Python type."""
    if token == "yes":
        return True
    if token == "no":
        return False
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _tokenize(text: str) -> list:
    """Tokenize PDXScript text into a flat list of (type, value) tuples.

    Types: 's' = string, 'b' = brace, 'o' = operator, 't' = token
    Comments are discarded. This runs at C speed via re.finditer.
    """
    tokens = []
    append = tokens.append  # local ref for speed
    for m in _TOKEN_RE.finditer(text):
        g1 = m.group(1)
        if g1 is not None:
            append(('s', g1[1:-1]))  # strip quotes
            continue
        g2 = m.group(2)
        if g2 is not None:
            append(('b', g2))
            continue
        g3 = m.group(3)
        if g3 is not None:
            append(('o', g3))
            continue
        g4 = m.group(4)
        if g4 is not None:
            append(('t', g4))
    return tokens


class PDXParser:
    """Parse PDXScript text into Python data structures.

    Uses fast regex tokenization followed by a single-pass recursive
    descent tree builder.
    """

    def __init__(self, text: str):
        # Strip SAV header line if present (Rakaly melted saves)
        if text.startswith('SAV'):
            nl = text.index('\n')
            text = text[nl + 1:]
        self._tokens = _tokenize(text)
        self._n = len(self._tokens)
        self._pos = 0

    def parse(self) -> dict:
        """Parse the entire text and return a dict."""
        return self._parse_pairs()

    # ---- internal recursive descent on token list ----

    def _parse_pairs(self) -> dict:
        """Parse key=value pairs until } or end of tokens."""
        result = {}
        tokens = self._tokens
        n = self._n
        while self._pos < n:
            typ, val = tokens[self._pos]
            if typ == 'b' and val == '}':
                return result

            self._pos += 1

            # Expect operator next for a key=value pair
            if self._pos < n and tokens[self._pos][0] == 'o':
                self._pos += 1  # consume operator
                pval = self._parse_value()
                key = val
                if key in result:
                    existing = result[key]
                    if isinstance(existing, list):
                        existing.append(pval)
                    else:
                        result[key] = [existing, pval]
                else:
                    result[key] = pval
            else:
                # No operator — bare value; backtrack so caller can handle
                self._pos -= 1
                return result

        return result

    def _parse_value(self) -> Any:
        """Parse a single value: block, string, or primitive token."""
        if self._pos >= self._n:
            return ""
        typ, val = self._tokens[self._pos]
        if typ == 'b' and val == '{':
            return self._parse_block()
        self._pos += 1
        if typ == 's':
            return val
        # Handle color literals: rgb { R G B } or hsv { H S V }
        converted = _convert(val)
        if val in ('rgb', 'hsv') and self._pos < self._n:
            ntyp, nval = self._tokens[self._pos]
            if ntyp == 'b' and nval == '{':
                block = self._parse_block()
                return val  # discard color values, keep as string label
        return converted

    def _parse_block(self) -> Any:
        """Parse a { ... } block as either a dict or array."""
        self._pos += 1  # skip '{'
        if self._pos >= self._n:
            return {}
        typ, val = self._tokens[self._pos]
        if typ == 'b' and val == '}':
            self._pos += 1
            return {}

        # Peek: if second token is an operator, parse as dict
        if self._pos + 1 < self._n and self._tokens[self._pos + 1][0] == 'o':
            result = self._parse_pairs()
        else:
            result = self._parse_array()

        # Consume closing brace
        if (self._pos < self._n
                and self._tokens[self._pos][0] == 'b'
                and self._tokens[self._pos][1] == '}'):
            self._pos += 1
        return result

    def _parse_array(self) -> Any:
        """Parse an array of values inside { }.

        If a key=value pair is encountered mid-array, switches to dict mode.
        """
        result = []
        tokens = self._tokens
        n = self._n
        while self._pos < n:
            typ, val = tokens[self._pos]
            if typ == 'b' and val == '}':
                return result
            # Detect key=value → switch to dict mode
            if self._pos + 1 < n and tokens[self._pos + 1][0] == 'o':
                d = self._parse_pairs()
                if not result:
                    return d
                # Rare: array followed by key=value pairs; return array
                return result
            result.append(self._parse_value())
        return result


def parse_pdx(text: str) -> dict:
    """Convenience function to parse PDXScript text."""
    parser = PDXParser(text)
    return parser.parse()
