from __future__ import annotations

from html5lib import html5parser as upstream
from html5lib.treebuilders import getTreeBuilder

from ._tokenizer import HTMLTokenizer


class HTMLParser(upstream.HTMLParser):
    def _parse(self, stream, innerHTML=False, container="div", scripting=False, **kwargs):
        self.innerHTMLMode = innerHTML
        self.container = container
        self.scripting = scripting
        self.tokenizer = HTMLTokenizer(stream, parser=self, **kwargs)
        self.reset()
        try:
            self.mainLoop()
        except upstream._ReparseException:
            self.reset()
            self.mainLoop()


def parse(doc, treebuilder="etree", namespaceHTMLElements=True, **kwargs):
    """Parse an HTML document; signature and result match ``html5lib.parse``."""
    tree = getTreeBuilder(treebuilder)
    return HTMLParser(tree=tree, namespaceHTMLElements=namespaceHTMLElements).parse(doc, **kwargs)


def parseFragment(doc, container="div", treebuilder="etree", namespaceHTMLElements=True, **kwargs):
    """Parse an HTML fragment; signature and result match ``html5lib.parseFragment``."""
    tree = getTreeBuilder(treebuilder)
    return HTMLParser(tree=tree, namespaceHTMLElements=namespaceHTMLElements).parseFragment(
        doc, container=container, **kwargs
    )
