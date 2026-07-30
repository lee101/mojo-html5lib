from __future__ import annotations

import math
import os
import platform
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import html5lib  # noqa: E402

import mojo_html5lib  # noqa: E402
from mojo_html5lib._lib import scan  # noqa: E402
from mojo_html5lib._tokenizer import HTMLTokenizer  # noqa: E402


def best_time(fn, repeat=3):
    best = math.inf
    for _ in range(repeat):
        start = time.perf_counter()
        value = fn()
        best = min(best, time.perf_counter() - start)
    return best, value


def corpus(rows):
    return "".join(
        f'<article class="item" data-id={i}><h2>Item {i}</h2>'
        f'<p>AT&amp;T value {i}</p><a href="/items/{i}">open</a></article>'
        for i in range(rows)
    )


def report(name, ours, upstream):
    ratio = upstream / ours
    status = "faster" if ratio >= 1 else "slower"
    print(f"| {name} | {ours * 1000:.1f} ms | {upstream * 1000:.1f} ms | {ratio:.2f}x {status} |")


def main():
    source = corpus(10_000)
    mojo_html5lib.parse("<p>warmup</p>")

    scan_time, records = best_time(lambda: scan(source))
    ours_tok, ours_tokens = best_time(lambda: list(HTMLTokenizer(source)))
    upstream_tok, upstream_tokens = best_time(
        lambda: list(html5lib._tokenizer.HTMLTokenizer(source))
    )
    assert ours_tokens == upstream_tokens

    ours_parse, ours_tree = best_time(lambda: mojo_html5lib.parse(source), repeat=2)
    upstream_parse, upstream_tree = best_time(lambda: html5lib.parse(source), repeat=2)
    assert len(list(ours_tree.iter())) == len(list(upstream_tree.iter()))

    print(f"Machine: {platform.processor() or platform.machine()}, {platform.platform()}")
    print(f"Corpus: {len(source) / 1_000_000:.2f} MB, {len(ours_tokens):,} tokens, {records[1].shape[0]:,} records")
    print()
    print("| operation | mojo-html5lib | html5lib 1.1 | ratio |")
    print("| --- | ---: | ---: | ---: |")
    report("HTMLTokenizer", ours_tok, upstream_tok)
    report("parse to etree", ours_parse, upstream_parse)
    print(f"| Mojo lexical scan only | {scan_time * 1000:.1f} ms | n/a | n/a |")


if __name__ == "__main__":
    main()
