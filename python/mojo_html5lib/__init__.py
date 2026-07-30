"""HTML5 tokenization accelerated by Mojo, with html5lib-compatible trees."""

from html5lib import getTreeBuilder, getTreeWalker, serialize

from .html5parser import HTMLParser, parse, parseFragment

__all__ = [
    "HTMLParser",
    "parse",
    "parseFragment",
    "getTreeBuilder",
    "getTreeWalker",
    "serialize",
]

__version__ = "0.1.0"
