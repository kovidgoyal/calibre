# Firefox-based stealth fallback (proposal)

> Draft proposal, opened because issues and discussions are disabled on this repo.

The current `Browser` class in `browser.py` subclasses `AsyncCamoufox` directly. Some target sites (notably newer Amazon metadata pages and some publisher product pages) flag camoufox's UA combination by default.

This proposal asks if it would be in scope to add an optional sibling class wrapping `invisible_playwright` (https://github.com/feder-cr/invisible_playwright), which drives a patched Firefox 150 binary (https://github.com/feder-cr/invisible_firefox, MPL-2, same license as Firefox upstream, fingerprint patches at the C++ source level so no JS shims to detect).

Same async API surface as `AsyncCamoufox`, so the `Warmup` and call sites would not change. Would be selected only when explicitly opted into via the existing automate config.

If accepted, follow-up PR adds the sibling class plus a config switch. Issues against the backend route to feder-cr/invisible_playwright, not here.

Closing this without noise if not in scope.
