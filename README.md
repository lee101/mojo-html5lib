# mojo-html5lib

`mojo-html5lib` is a Mojo-accelerated front end for
[html5lib](https://github.com/html5lib/html5lib-python). It preserves html5lib 1.1's
parser API and tree-building behavior while replacing the hot lexical scan for ordinary
ASCII HTML with a compiled Mojo kernel.

This is deliberately a hybrid port. Token boundary discovery is a tight byte-processing
loop and benefits from Mojo. HTML5 tree construction is pointer-heavy Python object
mutation governed by many insertion modes; this package reuses html5lib's mature tree
builders instead of duplicating that non-compute-bound code.

## Coverage

The public covered surface mirrors these html5lib names and signatures:

- `parse(doc, treebuilder="etree", namespaceHTMLElements=True, **kwargs)`
- `parseFragment(doc, container="div", treebuilder="etree", namespaceHTMLElements=True, **kwargs)`
- `HTMLParser(tree=None, strict=False, namespaceHTMLElements=True, debug=False)`
- `_tokenizer.HTMLTokenizer(stream, parser=None, **kwargs)`
- `getTreeBuilder`, `getTreeWalker`, and `serialize`

The Mojo fast path handles well-formed ASCII text runs, whitespace, start and end tags,
quoted and unquoted attributes, duplicate attributes, self-closing tags, comments, simple
doctypes, and semicolon-terminated named and numeric character references. Tree output
is tested with html5lib's `etree` and `dom` builders, including fragments, namespaces,
foster parenting, foreign content, and implied elements. Other upstream tree builders
are exposed by `getTreeBuilder` but are not covered by this package's test environment.

Inputs requiring stateful raw-text tokenization (`script`, `style`, `title`, `textarea`,
and related elements), non-ASCII decoding, encoding changes, complex doctypes, ambiguous
entities, malformed lexical constructs, or file/byte-stream handling transparently use
html5lib's tokenizer. Those cases remain correct, but do not receive tokenizer speedups.
This release does not reimplement serializers, tree walkers, sanitizer filters, or the
HTML5 insertion-mode tree builder in Mojo.

## Install and build

The checked-in Pixi environment pins the Mojo nightly used by the source.

```bash
pixi install
pixi run build
pixi run test
```

The build produces `dist/libmojo-html5lib.so`. `html5lib` is a runtime dependency as well
as the parity reference.

## Usage

```python
import xml.etree.ElementTree as ET
import mojo_html5lib as html5lib

document = html5lib.parse(
    '<!doctype html><main><p class="lead">Hello &amp; goodbye</p></main>'
)
print(ET.tostring(document, encoding="unicode"))

fragment = html5lib.parseFragment("<b>one</b> and <i>two</i>", container="div")
print(ET.tostring(fragment, encoding="unicode"))
```

For code that imports the tokenizer directly:

```python
from mojo_html5lib._tokenizer import HTMLTokenizer

tokens = list(HTMLTokenizer('<a href="/docs">Docs</a>'))
```

## Benchmarks

Measured with `pixi run bench` on Linux 6.8.0-136-generic x86-64, glibc 2.39. The
generated corpus was 1.19 MB of attribute- and entity-bearing article markup, producing
130,000 html5lib tokens and 160,000 lexical records. Times are the best of three runs
(tree parsing uses two because it allocates a full tree).

| operation | mojo-html5lib | html5lib 1.1 | ratio |
| --- | ---: | ---: | ---: |
| `HTMLTokenizer` | 257.9 ms | 1083.5 ms | 4.20x faster |
| parse to etree | 1253.7 ms | 2064.3 ms | 1.65x faster |
| Mojo lexical scan only | 13.4 ms | n/a | n/a |

The scanner itself is much faster than end-to-end tokenization. Python dictionary
construction and HTML5 tree mutation dominate the remaining time, so the full parser
speedup is intentionally reported rather than extrapolated from the kernel.

Contiguous text and quoted-attribute searches use native-width `UInt8` SIMD loads with
an unaligned-safe load and a scalar remainder loop. Parsing remains serial: token
boundaries depend on preceding lexical state, and html5lib tree construction mutates one
ordered open-element stack, leaving no large independent work units that would repay
thread-launch overhead.

There is no GPU path. The scanner performs byte comparisons and span writes with low
arithmetic intensity, while tree construction is branch-heavy Python object mutation.
Moving the input and records between host and device would add work to the portion this
package is intended to shorten.

## How it works

Python first keeps the input as an immutable ASCII `bytes` buffer. Through `ctypes`, it
passes that buffer's address and length to one C-ABI Mojo export. Python first requests
a record count and allocates the exact output array. On the fill call, Mojo re-counts to
validate that capacity and then writes the records. The export rejects null pointers,
negative lengths, and insufficient output capacity before accessing the corresponding
buffer.

Each lexical record is five contiguous native 64-bit integers:
`(kind, begin, end, value_begin, value_end)`. Spans point into the original byte buffer;
text is not copied across the FFI boundary. Python slices the original ASCII string at
those same offsets instead of decoding byte slices. Start-tag records are followed by
attribute records, and one flag slot carries self-closing state. Standalone tokenizers
materialize their result directly; parser-owned tokenizers validate the complete record
set and then stream dictionaries into the existing insertion-mode parser, avoiding a
second full token list. Unsupported input is detected before any partial token stream is
exposed and is parsed from the original source by upstream html5lib.

MIT.
