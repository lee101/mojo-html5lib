from __future__ import annotations

from html import unescape
from html.entities import html5 as html_entities
import re

from html5lib import _tokenizer as upstream
from html5lib.constants import tokenTypes

from ._lib import scan

_ENTITY = re.compile(r"&(?:#[0-9]+|#[xX][0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);")
_CHARACTERS = tokenTypes["Characters"]
_SPACE_CHARACTERS = tokenTypes["SpaceCharacters"]
_START_TAG = tokenTypes["StartTag"]
_END_TAG = tokenTypes["EndTag"]
_COMMENT = tokenTypes["Comment"]
_DOCTYPE = tokenTypes["Doctype"]
_PARSE_ERROR = tokenTypes["ParseError"]
_ATTRIBUTE = 8
_ENTITY_RECORD = 10


def _decode_entity(raw: str) -> str | None:
    if raw.startswith("&#"):
        digits = raw[2:-1]
        base = 10
        if digits[:1] in ("x", "X"):
            digits = digits[1:]
            base = 16
        try:
            codepoint = int(digits, base)
        except ValueError:
            return None
        if (
            codepoint == 0
            or 0xD800 <= codepoint <= 0xDFFF
            or codepoint > 0x10FFFF
            or 0x0001 <= codepoint <= 0x0008
            or 0x000E <= codepoint <= 0x001F
            or 0x007F <= codepoint <= 0x009F
            or 0xFDD0 <= codepoint <= 0xFDEF
            or codepoint & 0xFFFF in (0xFFFE, 0xFFFF)
        ):
            return None
    elif raw[1:] not in html_entities:
        return None
    decoded = unescape(raw)
    if decoded == raw:
        return None
    return decoded


def _decode_entities(value: str) -> str | None:
    if "&" not in value:
        return value
    cursor = 0
    parts = []
    for match in _ENTITY.finditer(value):
        if "&" in value[cursor:match.start()]:
            return None
        raw = match.group()
        decoded = _decode_entity(raw)
        if decoded is None:
            return None
        parts.append(value[cursor:match.start()])
        parts.append(decoded)
        cursor = match.end()
    if "&" in value[cursor:]:
        return None
    parts.append(value[cursor:])
    return "".join(parts)


class HTMLTokenizer(upstream.HTMLTokenizer):
    """html5lib-compatible tokenizer with a Mojo fast path for ordinary ASCII."""

    def __init__(self, stream, parser=None, **kwargs):
        self._source = stream if isinstance(stream, str) else None
        self.used_mojo = False
        super().__init__(stream, parser=parser, **kwargs)

    def _fast_tokens(self):
        if self._source is None:
            return None
        scanned = scan(self._source)
        if scanned is None:
            return None
        _, records = scanned
        rows = records.tolist()
        if self.parser is None:
            tokens = self._list_fast_tokens(self._source, rows)
            return None if tokens is None else iter(tokens)
        for record in rows:
            kind, begin, end, value_begin, value_end = record
            if kind == _ENTITY_RECORD:
                decoded = _decode_entity(self._source[begin:end])
                if decoded is None:
                    return None
                record[3] = decoded
            elif kind == _ATTRIBUTE:
                value = self._source[value_begin:value_end]
                if "&" in value:
                    value = _decode_entities(value)
                    if value is None:
                        return None
                decoded = value
                record[3] = decoded
        return self._iter_fast_tokens(self._source, rows)

    @staticmethod
    def _list_fast_tokens(source, rows):
        tokens = []
        row = 0
        while row < len(rows):
            kind, begin, end, flag, _ = rows[row]
            text = source[begin:end]
            if kind == _CHARACTERS or kind == _SPACE_CHARACTERS:
                tokens.append({"type": kind, "data": text})
            elif kind == _ENTITY_RECORD:
                decoded = _decode_entity(text)
                if decoded is None:
                    return None
                tokens.append({"type": _CHARACTERS, "data": decoded})
            elif kind == _COMMENT:
                tokens.append({"type": kind, "data": text})
            elif kind == _DOCTYPE:
                tokens.append({
                    "type": kind,
                    "name": text.lower(),
                    "publicId": None,
                    "systemId": None,
                    "correct": True,
                })
            elif kind == _END_TAG:
                tokens.append({
                    "type": kind,
                    "name": text.lower(),
                    "data": [],
                    "selfClosing": False,
                })
            elif kind == _START_TAG:
                attrs = {}
                errors = []
                row += 1
                while row < len(rows) and rows[row][0] == _ATTRIBUTE:
                    _, nb, ne, value_begin, value_end = rows[row]
                    name = source[nb:ne].lower()
                    value = source[value_begin:value_end]
                    if "&" in value:
                        value = _decode_entities(value)
                        if value is None:
                            return None
                    if name in attrs:
                        errors.append({"type": _PARSE_ERROR, "data": "duplicate-attribute"})
                    else:
                        attrs[name] = value
                    row += 1
                tokens.extend(errors)
                tokens.append({
                    "type": kind,
                    "name": text.lower(),
                    "data": attrs,
                    "selfClosing": bool(flag),
                    "selfClosingAcknowledged": False,
                })
                continue
            else:
                raise RuntimeError(f"unexpected Mojo record kind {kind}")
            row += 1
        return tokens

    @staticmethod
    def _iter_fast_tokens(source, rows):
        row = 0
        while row < len(rows):
            kind, begin, end, flag, _ = rows[row]
            text = source[begin:end]
            if kind == _CHARACTERS or kind == _SPACE_CHARACTERS:
                yield {"type": kind, "data": text}
            elif kind == _ENTITY_RECORD:
                yield {"type": _CHARACTERS, "data": flag}
            elif kind == _COMMENT:
                yield {"type": kind, "data": text}
            elif kind == _DOCTYPE:
                yield {
                    "type": kind,
                    "name": text.lower(),
                    "publicId": None,
                    "systemId": None,
                    "correct": True,
                }
            elif kind == _END_TAG:
                yield {
                    "type": kind,
                    "name": text.lower(),
                    "data": [],
                    "selfClosing": False,
                }
            elif kind == _START_TAG:
                attrs = {}
                errors = []
                row += 1
                while row < len(rows) and rows[row][0] == _ATTRIBUTE:
                    _, nb, ne, value, _ = rows[row]
                    name = source[nb:ne].lower()
                    if name in attrs:
                        errors.append({"type": _PARSE_ERROR, "data": "duplicate-attribute"})
                    else:
                        attrs[name] = value
                    row += 1
                yield from errors
                yield {
                    "type": kind,
                    "name": text.lower(),
                    "data": attrs,
                    "selfClosing": bool(flag),
                    "selfClosingAcknowledged": False,
                }
                continue
            else:
                raise RuntimeError(f"unexpected Mojo record kind {kind}")
            row += 1

    def __iter__(self):
        tokens = self._fast_tokens()
        if tokens is None:
            return super().__iter__()
        self.used_mojo = True
        return tokens
