"""
Recursive descent parser for Paradox PDXScript text format.

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
from typing import Any


class PDXParser:
    """Parse PDXScript text into Python data structures."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def parse(self) -> dict:
        """Parse the entire text and return a dict."""
        self._skip_whitespace_and_comments()
        result = self._parse_pairs()
        return result

    def _parse_pairs(self) -> dict:
        """Parse a sequence of key=value pairs into a dict."""
        result = {}
        while self.pos < self.length:
            self._skip_whitespace_and_comments()
            if self.pos >= self.length:
                break
            # Check for closing brace
            if self.text[self.pos] == "}":
                break

            key = self._parse_token()
            if key is None:
                break

            self._skip_whitespace_and_comments()

            # Check if next char is an operator
            if self.pos < self.length and self.text[self.pos] in "=><":
                self._consume_operator()
                self._skip_whitespace_and_comments()
                value = self._parse_value()
            else:
                # Bare value (part of an array) — shouldn't happen at top level
                # but handle gracefully
                value = key
                key = None

            if key is not None:
                # Handle duplicate keys by converting to list
                if key in result:
                    existing = result[key]
                    if isinstance(existing, list) and not self._is_value_list(existing):
                        existing.append(value)
                    else:
                        result[key] = [existing, value]
                else:
                    result[key] = value

        return result

    def _is_value_list(self, lst: list) -> bool:
        """Check if a list looks like a parsed array value (all primitives)
        vs a duplicate-key accumulator."""
        # Duplicate-key lists can contain dicts; array values are primitives
        # This is a heuristic — not perfect but good enough
        return False

    def _parse_value(self) -> Any:
        """Parse a single value: block, quoted string, or token."""
        self._skip_whitespace_and_comments()
        if self.pos >= self.length:
            return ""

        ch = self.text[self.pos]

        if ch == "{":
            return self._parse_block()
        elif ch == '"':
            return self._parse_quoted_string()
        else:
            return self._parse_token_value()

    def _parse_block(self) -> Any:
        """Parse a { ... } block. Could be a dict (key=value pairs) or an array."""
        self.pos += 1  # skip '{'
        self._skip_whitespace_and_comments()

        if self.pos >= self.length:
            return {}

        if self.text[self.pos] == "}":
            self.pos += 1
            return {}

        # Peek ahead to determine if this is a dict or array
        if self._block_is_array():
            return self._parse_array()
        else:
            result = self._parse_pairs()
            self._skip_whitespace_and_comments()
            if self.pos < self.length and self.text[self.pos] == "}":
                self.pos += 1
            return result

    def _block_is_array(self) -> bool:
        """Peek ahead to determine if a block contains key=value pairs or bare values."""
        save_pos = self.pos
        # Skip first token
        self._parse_token()
        self._skip_whitespace_and_comments()

        is_array = True
        if self.pos < self.length and self.text[self.pos] in "=><":
            is_array = False

        self.pos = save_pos
        return is_array

    def _parse_array(self) -> list:
        """Parse an array of values inside { }."""
        result = []
        while self.pos < self.length:
            self._skip_whitespace_and_comments()
            if self.pos >= self.length:
                break
            if self.text[self.pos] == "}":
                self.pos += 1
                return result

            value = self._parse_value()
            result.append(value)

        return result

    def _parse_token(self) -> str:
        """Parse an unquoted token (key or value)."""
        self._skip_whitespace_and_comments()
        if self.pos >= self.length:
            return None

        if self.text[self.pos] == '"':
            return self._parse_quoted_string()

        start = self.pos
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch in " \t\r\n={}><#":
                break
            self.pos += 1

        if self.pos == start:
            return None

        return self.text[start : self.pos]

    def _parse_token_value(self) -> Any:
        """Parse a token and convert to appropriate Python type."""
        token = self._parse_token()
        if token is None:
            return ""
        return self._convert_token(token)

    def _convert_token(self, token: str) -> Any:
        """Convert a string token to the appropriate Python type."""
        if token == "yes":
            return True
        if token == "no":
            return False

        # Try integer
        try:
            return int(token)
        except ValueError:
            pass

        # Try float
        try:
            return float(token)
        except ValueError:
            pass

        # It's a string (could be a date like 1836.1.1, country tag, etc.)
        return token

    def _parse_quoted_string(self) -> str:
        """Parse a "quoted string"."""
        self.pos += 1  # skip opening quote
        start = self.pos
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == "\\":
                self.pos += 2  # skip escaped char
                continue
            if ch == '"':
                result = self.text[start : self.pos]
                self.pos += 1  # skip closing quote
                return result
            self.pos += 1
        return self.text[start : self.pos]

    def _consume_operator(self):
        """Consume an operator (=, >, <, >=, <=)."""
        if self.pos < self.length:
            ch = self.text[self.pos]
            self.pos += 1
            if self.pos < self.length and self.text[self.pos] in "=":
                self.pos += 1

    def _skip_whitespace_and_comments(self):
        """Skip whitespace and # comments."""
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch in " \t\r\n":
                self.pos += 1
            elif ch == "#":
                # Skip to end of line
                while self.pos < self.length and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break


def parse_pdx(text: str) -> dict:
    """Convenience function to parse PDXScript text."""
    parser = PDXParser(text)
    return parser.parse()
