/**
 * Parser for Paradox PDXScript text format.
 *
 * Uses regex-based tokenization then builds the tree in a single pass.
 * Handles: key=value pairs, nested blocks, arrays, quoted/unquoted strings,
 * numbers, dates (as strings), yes/no booleans, duplicate keys (→ arrays),
 * operators: = > < >= <=
 */

import type { ParsedData, ParsedValue } from './types';

const enum TokenKind {
  String,
  Brace,
  Operator,
  Text,
}

interface Token {
  kind: TokenKind;
  value: string;
}

const TOKEN_RE =
  /\#[^\n]*|("(?:[^"\\]|\\.)*")|([{}])|([=><]=?)|([^\s={}><\#"]+)/g;

function coerce(raw: string): string | number | boolean {
  if (raw === 'yes') return true;
  if (raw === 'no') return false;
  const asInt = parseInt(raw, 10);
  if (String(asInt) === raw) return asInt;
  const asFloat = parseFloat(raw);
  if (!isNaN(asFloat) && /^-?\d+\.\d+$/.test(raw)) return asFloat;
  return raw;
}

function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  let m: RegExpExecArray | null;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(text)) !== null) {
    if (m[1] !== undefined) {
      tokens.push({ kind: TokenKind.String, value: m[1].slice(1, -1) });
    } else if (m[2] !== undefined) {
      tokens.push({ kind: TokenKind.Brace, value: m[2] });
    } else if (m[3] !== undefined) {
      tokens.push({ kind: TokenKind.Operator, value: m[3] });
    } else if (m[4] !== undefined) {
      tokens.push({ kind: TokenKind.Text, value: m[4] });
    }
  }
  return tokens;
}

class PDXParser {
  private readonly tokens: Token[];
  private readonly length: number;
  private pos: number;

  constructor(text: string) {
    // Strip SAV header line if present (Rakaly melted saves)
    if (text.startsWith('SAV')) {
      const newline = text.indexOf('\n');
      text = text.substring(newline + 1);
    }
    this.tokens = tokenize(text);
    this.length = this.tokens.length;
    this.pos = 0;
  }

  parse(): ParsedData {
    return this.parsePairs();
  }

  private parsePairs(): ParsedData {
    const result: ParsedData = {};
    while (this.pos < this.length) {
      const token = this.tokens[this.pos];
      if (token.kind === TokenKind.Brace && token.value === '}') return result;

      this.pos++;

      if (this.pos < this.length && this.tokens[this.pos].kind === TokenKind.Operator) {
        this.pos++; // consume operator
        const value = this.parseValue();
        const key = token.value;
        if (key in result) {
          const existing = result[key];
          if (Array.isArray(existing)) {
            existing.push(value);
          } else {
            result[key] = [existing, value];
          }
        } else {
          result[key] = value;
        }
      } else {
        this.pos--;
        return result;
      }
    }
    return result;
  }

  private parseValue(): ParsedValue {
    if (this.pos >= this.length) return '';
    const token = this.tokens[this.pos];
    if (token.kind === TokenKind.Brace && token.value === '{') return this.parseBlock();
    this.pos++;
    if (token.kind === TokenKind.String) return token.value;
    const converted = coerce(token.value);
    // Handle color literals: rgb { R G B } or hsv { H S V }
    if (
      (token.value === 'rgb' || token.value === 'hsv') &&
      this.pos < this.length
    ) {
      const next = this.tokens[this.pos];
      if (next.kind === TokenKind.Brace && next.value === '{') {
        this.parseBlock(); // discard color values
        return token.value;
      }
    }
    return converted;
  }

  private parseBlock(): ParsedValue {
    this.pos++; // skip '{'
    if (this.pos >= this.length) return {};
    const token = this.tokens[this.pos];
    if (token.kind === TokenKind.Brace && token.value === '}') {
      this.pos++;
      return {};
    }

    let result: ParsedValue;
    if (
      this.pos + 1 < this.length &&
      this.tokens[this.pos + 1].kind === TokenKind.Operator
    ) {
      result = this.parsePairs();
    } else {
      result = this.parseArray();
    }

    // Consume closing brace
    if (
      this.pos < this.length &&
      this.tokens[this.pos].kind === TokenKind.Brace &&
      this.tokens[this.pos].value === '}'
    ) {
      this.pos++;
    }
    return result;
  }

  private parseArray(): ParsedValue {
    const result: ParsedValue[] = [];
    while (this.pos < this.length) {
      const token = this.tokens[this.pos];
      if (token.kind === TokenKind.Brace && token.value === '}') return result;
      // Detect key=value → switch to dict mode
      if (
        this.pos + 1 < this.length &&
        this.tokens[this.pos + 1].kind === TokenKind.Operator
      ) {
        const pairs = this.parsePairs();
        if (result.length === 0) return pairs;
        return result;
      }
      result.push(this.parseValue());
    }
    return result;
  }
}

export function parsePdx(text: string): ParsedData {
  return new PDXParser(text).parse();
}
