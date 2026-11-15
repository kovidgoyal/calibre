# Deep TOC performance corpus

Shared generators and gated tests for check/auto-fix (line A) and MD→EPUB /
DetectStructure TOC (line B). Design: Context `docs/toc-perf-design.md`.

## Scales

| Scale | N | Fanout (depth 3) |
|-------|---|------------------|
| Tiny | 20 | 2×2×5 |
| S | 100 | 10×10×1 |
| M | 500 | 10×10×5 |
| L | 2000 | 10×10×20 |
| XL | 8000 | 10×10×80 |

N must be divisible by 100 (except Tiny). Convert stays depth 3 at all scales.

## Material A (editor check / fix)

Built as EPUB3 under the polish-test cache (`get_cache()/toc_perf/`), not committed.

| Variant | Purpose |
|---------|---------|
| A-dangling | nav+NCX → same `missing.xhtml` |
| A-case | wrong-case paths → real `chapter.xhtml` (case-sensitive FS) |
| A-dual | nav+NCX same dangling set |
| A-mixed | dangling + case + BadDestinationFragment |
| A-clean | valid deep dual TOC |
| A-invalid-id | invalid `_frag` ids in HTML (+ shared id on chapter2) + CSS; TOC hrefs use those fragments (A3/R5) |

**Case-sensitive FS required** for A-case (Linux CI). On macOS/Windows default FS, A-case tests skip.

## Material B (convert)

| Variant | Purpose | PR |
|---------|---------|-----|
| B-levels | h1/h2/h3 HTML or MD | B1 |
| B-playorder | same artifact as B-levels; API tests | B1 |
| B-sony | stub → Sony quirk indexing | B2 |
| B-inline | stub → TOCAdder `nodes` vs `count()` | B2 |

Convert options in tests: `--level1-toc=//h:h1 --level2-toc=//h:h2 --level3-toc=//h:h3`.

## Gates

Hard CI asserts are **call counts** (and correctness), not wall-time ratios.

Until a product PR enables a gate, tests honor:

- `CALIBRE_TOC_PERF_GATES=1` — force hard asserts (fail if unimplemented)
- otherwise A1 gates are hard once product lands; B1/B2 may use `@expectedFailure` until their PR

Baseline wall times for L: `baselines.json` / `test_baselines.py` — **no ratio assert**.

## Run

```bash
source ~/.calibre-dev-env
cd /path/to/calibre
export PATH="$PWD/develop:$PATH" QT_QPA_PLATFORM=offscreen
python setup.py test --test-module=calibre.ebooks.oeb.polish.tests.toc_perf
# or:
calibre-debug -c "from calibre.ebooks.oeb.polish.tests.main import find_tests; ..."
```
