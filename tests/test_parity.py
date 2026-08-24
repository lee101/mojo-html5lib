from __future__ import annotations

import io
import ctypes
import xml.etree.ElementTree as ET

import html5lib
import pytest

import mojo_html5lib
from mojo_html5lib._lib import lib, scan
from mojo_html5lib._tokenizer import HTMLTokenizer


FAST_DOCUMENTS = [
    "<p>Hello, world!</p>",
    '<!doctype html><main id="content" hidden><h1>Title</h1><p>Body</p></main>',
    "<!-- before --><ul><li>one</li><li>two</li></ul><!-- after -->",
    '<form action="/submit" method=post><input name=q value="Mojo HTML"><button>Go</button></form>',
    "<p>AT&amp;T &lt; 10 &#65; &#x42;</p>",
    '<a title="AT&amp;T &#65;">entity attribute</a>',
    "<table><tr><th>A<th>B<tr><td>1<td>2</table>",
    "<p>one<div>two</div>three",
    "<ol><li>first<li>second<li>third</ol>",
    "<select><option>A<option selected>B</select>",
    '<svg viewBox="0 0 10 10"><circle cx=5 cy=5 r=4 /></svg>',
]

FALLBACK_DOCUMENTS = [
    "<title>A &amp; B</title><p>x</p>",
    "<script>if (a < b) x++;</script>",
    "<noscript><p>fallback</p></noscript>",
    "<textarea>&lt;b&gt;</textarea>",
    "<p>café 日本語</p>",
    "<p>&copy without semicolon</p>",
    "<p title='&notanentity;'>fallback</p>",
    "<!DOCTYPE html PUBLIC>",
    "<p a='unterminated>",
    "<!-- invalid--comment -->",
    "<p>&#0;</p>",
    "<p>&#11;</p>",
    b"<meta charset=utf-8><p>\xc3\xa9</p>",
]


def etree_bytes(node):
    return ET.tostring(node, encoding="utf-8")


@pytest.mark.parametrize("source", FAST_DOCUMENTS)
def test_fast_tokenizer_exactly_matches_html5lib(source):
    ours = HTMLTokenizer(source)
    got = list(ours)
    expected = list(html5lib._tokenizer.HTMLTokenizer(source))
    assert ours.used_mojo
    assert got == expected


@pytest.mark.parametrize("source", FALLBACK_DOCUMENTS)
def test_fallback_tokenizer_exactly_matches_html5lib(source):
    ours = HTMLTokenizer(source)
    got = list(ours)
    expected = list(html5lib._tokenizer.HTMLTokenizer(source))
    assert not ours.used_mojo
    assert got == expected


@pytest.mark.parametrize("source", FAST_DOCUMENTS + FALLBACK_DOCUMENTS)
def test_document_tree_matches_html5lib(source):
    got = mojo_html5lib.parse(source, treebuilder="etree")
    expected = html5lib.parse(source, treebuilder="etree")
    assert etree_bytes(got) == etree_bytes(expected)


@pytest.mark.parametrize(
    ("source", "container"),
    [
        ("<b>bold</b> tail", "div"),
        ("<tr><td>A<td>B", "table"),
        ("<option>A<option>B", "select"),
        ("plain &amp; text", "p"),
        ("<svg><circle /></svg>", "div"),
    ],
)
def test_fragment_tree_matches_html5lib(source, container):
    got = mojo_html5lib.parseFragment(source, container=container)
    expected = html5lib.parseFragment(source, container=container)
    assert etree_bytes(got) == etree_bytes(expected)


def test_dom_treebuilder_matches_html5lib():
    source = "<!doctype html><!--x--><p class=x>Hello<br>world"
    got = mojo_html5lib.parse(source, treebuilder="dom")
    expected = html5lib.parse(source, treebuilder="dom")
    assert got.toxml() == expected.toxml()


def test_namespace_option_matches_html5lib():
    source = "<html><body><svg><foreignObject><p>x</p></foreignObject></svg></body></html>"
    got = mojo_html5lib.parse(source, namespaceHTMLElements=False)
    expected = html5lib.parse(source, namespaceHTMLElements=False)
    assert etree_bytes(got) == etree_bytes(expected)


def test_duplicate_attribute_error_and_first_value_match():
    source = "<p A=first a=second>x</p>"
    assert list(HTMLTokenizer(source)) == list(html5lib._tokenizer.HTMLTokenizer(source))


def test_fast_named_and_numeric_entity_decoding_matches_html5lib():
    source = "<p>&NotEqualTilde; &#x1F642; &#65;</p>"
    tokenizer = HTMLTokenizer(source)
    assert list(tokenizer) == list(html5lib._tokenizer.HTMLTokenizer(source))
    assert tokenizer.used_mojo


def test_file_like_input_uses_compatible_fallback():
    source = io.BytesIO(b"<p class=x>bytes</p>")
    got = mojo_html5lib.parse(source)
    expected = html5lib.parse(io.BytesIO(b"<p class=x>bytes</p>"))
    assert etree_bytes(got) == etree_bytes(expected)


def test_scanner_records_tag_attribute_and_text_spans():
    result = scan('<a href="/x">link</a>')
    assert result is not None
    _, records = result
    assert records[:, 0].tolist() == [3, 8, 1, 4]
    assert records[0, 1:3].tolist() == [1, 2]
    assert records[1, 3:5].tolist() == [9, 11]


def test_scanner_rejects_non_ascii_for_fallback():
    assert scan("<p>é</p>") is None


def test_ffi_rejects_invalid_addresses_lengths_and_output_capacity():
    scanner = lib().mh5_scan
    source = ctypes.create_string_buffer(b"<p>x</p>")
    address = ctypes.addressof(source)
    assert scanner(0, len(source.value), 0, 0) == -2
    assert scanner(address, -1, 0, 0) == -2
    assert scanner(0, 0, 0, 0) == 0

    count = scanner(address, len(source.value), 0, 0)
    output = (ctypes.c_int64 * (count * 5))()
    assert scanner(address, len(source.value), ctypes.addressof(output), count - 1) == -2
    assert scanner(address, len(source.value), ctypes.addressof(output), count) == count


def test_scanner_simd_tail_matches_html5lib():
    source = '<p data-value="' + ("v" * 67) + '">' + ("text" * 17) + "</p>"
    tokenizer = HTMLTokenizer(source)
    assert list(tokenizer) == list(html5lib._tokenizer.HTMLTokenizer(source))
    assert tokenizer.used_mojo


def test_scanner_simd_tail_rejects_invalid_input():
    assert scan("<p>" + ("x" * 67) + "\0tail</p>") is None


@pytest.mark.parametrize(
    "tag",
    [
        "title",
        "textarea",
        "style",
        "xmp",
        "iframe",
        "noembed",
        "noframes",
        "noscript",
        "SCRIPT",
        "plaintext",
        "meta",
    ],
)
def test_stateful_string_input_uses_fallback(tag):
    source = f"<{tag}>content</{tag}>"
    tokenizer = HTMLTokenizer(source)
    assert list(tokenizer) == list(html5lib._tokenizer.HTMLTokenizer(source))
    assert not tokenizer.used_mojo


def test_parser_class_reports_mojo_path():
    parser = mojo_html5lib.HTMLParser()
    parser.parse("<section><p>fast</p></section>")
    assert parser.tokenizer.used_mojo


def test_public_exports_match_html5lib_surface():
    assert callable(mojo_html5lib.parse)
    assert callable(mojo_html5lib.parseFragment)
    assert callable(mojo_html5lib.getTreeBuilder)
    assert callable(mojo_html5lib.getTreeWalker)
    assert callable(mojo_html5lib.serialize)


def test_exported_tree_walker_and_serializer_work_together():
    tree = mojo_html5lib.parseFragment("<b>one</b> &amp; <i>two</i>")
    walker = mojo_html5lib.getTreeWalker("etree")
    events = list(walker(tree))
    assert any(event["type"] == "StartTag" and event["name"] == "b" for event in events)
    assert mojo_html5lib.serialize(tree, tree="etree") == "<b>one</b> &amp; <i>two</i>"
