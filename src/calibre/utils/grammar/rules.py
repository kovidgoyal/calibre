#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Grammar, style and typography checking for many languages using the
# deterministic rules of LanguageTool, via langtool. langtool downloads the
# dictionaries a language needs on demand. These, and its cache of derived
# data, are kept in the calibre cache directory. Checks never download
# anything, instead LanguageDataNotDownloaded is raised, so that downloading
# can be done with a progress report.

import os
from collections import OrderedDict
from collections.abc import Callable, Sequence
from functools import lru_cache
from threading import Event, Lock
from types import ModuleType
from typing import Literal, NamedTuple, Protocol, cast

from calibre.utils.grammar.models import DownloadAborted

# Increment when changes to this module change the results of checks, so that
# cached results are discarded
RULES_VERSION = 1
MAX_CACHED_TOOLS = 4
IssueSource = Literal['rules', 'model']


class Issue(NamedTuple):
    # Offsets into the checked text of the text with the issue. start == end
    # means something is missing at that position.
    start: int
    end: int
    # Possible replacements for the text, best first. Can be empty.
    replacements: tuple[str, ...]
    message: str
    short_message: str
    # The id of the rule that found the issue, can be used to disable it
    rule_id: str
    category: str
    # The kind of issue in lowercase, for example: grammar, misspelling, style,
    # typographical, uncategorized
    issue_type: str
    # A link to an explanation of the issue, can be empty
    url: str
    source: IssueSource = 'rules'


class RuleOptions(NamedTuple):
    disabled_rules: tuple[str, ...] = ()
    # Rules that are off by default to turn on
    enabled_rules: tuple[str, ...] = ()
    disabled_categories: tuple[str, ...] = ()
    # Also use rules that find stylistic issues that are not errors
    picky: bool = False

    def normalized(self) -> RuleOptions:
        return RuleOptions(
            tuple(sorted(set(self.disabled_rules))), tuple(sorted(set(self.enabled_rules))), tuple(sorted(set(self.disabled_categories))), self.picky
        )

    @property
    def cache_key(self) -> str:
        n = self.normalized()
        return f'{",".join(n.disabled_rules)}|{",".join(n.enabled_rules)}|{",".join(n.disabled_categories)}|{int(n.picky)}'


DEFAULT_RULE_OPTIONS = RuleOptions()


class LanguageDataNotDownloaded(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f'The data needed to check the language {code} has not been downloaded')


class UnsupportedRulesLanguage(ValueError):
    def __init__(self, lang: str):
        self.lang = lang
        super().__init__(f'Grammar checking is not supported for the language: {lang}')


# Typing for the parts of langtool that are used {{{


class LTMatch(Protocol):
    offset: int
    length: int
    rule_id: str
    message: str
    short_message: str
    replacements: list[str]
    category: str | None
    issue_type: str | None
    url: str | None


class LTTool(Protocol):
    def check(self, text: str) -> list[LTMatch]: ...
    def sentences(self, text: str) -> list[str]: ...
    def disable_rules(self, rule_ids: Sequence[str]) -> None: ...
    def enable_rule(self, rule_id: str) -> None: ...
    def disable_category(self, category_id: str) -> None: ...


class LTSource(NamedTuple):
    size: int
    names: tuple[str, ...]


# }}}

_configure_lock = Lock()
_configured = False


def langtool_cache_dir() -> str:
    from calibre.constants import cache_dir

    return os.path.join(cache_dir(), 'grammar', 'langtool')


def get_langtool() -> ModuleType:
    """Return the langtool module, configured to use the calibre cache directory"""
    global _configured
    import langtool

    with _configure_lock:
        if not _configured:
            langtool.set_cache_dir(langtool_cache_dir())
            _configured = True
    return langtool


def langtool_version() -> str:
    return str(get_langtool().__version__)


@lru_cache(2)
def supported_codes() -> tuple[str, ...]:
    return tuple(str(x) for x in get_langtool().languages())


@lru_cache(64)
def langtool_code(lang: str | None) -> str | None:
    """
    Return the langtool language code for a language code such as en, en_GB,
    pt-BR or eng, or None if the language is not supported. A region is used
    only if langtool has a variant for it, a language without a region uses the
    variant that is not specific to any region, if there is one.
    """
    parts = (lang or 'en').replace('_', '-').split('-')
    base = parts[0].lower()
    if len(base) == 3:
        from calibre.utils.localization import lang_as_iso639_1

        base = lang_as_iso639_1(base) or base
    region = parts[1].upper() if len(parts) > 1 and len(parts[1]) == 2 else ''
    codes = supported_codes()
    if region and (q := f'{base}-{region}') in codes:
        return q
    if base in codes:
        return base
    variants = [c for c in codes if c.split('-')[0] == base]
    if not variants:
        return None
    # For languages such as pl, which only has pl-PL, prefer the variant
    # of the country with the same code as the language
    primary = f'{base}-{base.upper()}'
    return primary if primary in variants else variants[0]


def code_for(lang: str | None) -> str:
    if (code := langtool_code(lang)) is None:
        raise UnsupportedRulesLanguage(lang or 'en')
    return code


# Downloading {{{
# TODO: Use the progress hook, url opener and downloads_needed()/is_ready() APIs
# once they are available in langtool, instead of its internals


def resource_language(code: str) -> str:
    lt = get_langtool()
    rl = lt.get_language(code).definition.get('resource_language') or code
    return str(rl).split('-')[0]


def pending_downloads(lang: str | None) -> list[LTSource]:
    from langtool import dictionaries

    get_langtool()
    base = resource_language(code_for(lang))
    sources: list[dict[str, object]] = dictionaries.manifest()['languages'].get(base) or []
    cdir = str(dictionaries.cache_dir())
    ans = []
    for src in sources:
        files = cast('list[dict[str, object]]', src['files'])
        names = tuple(str(f['name']) for f in files)
        if not all(os.path.exists(str(dictionaries.join_name(cdir, n))) for n in names):
            ans.append(LTSource(int(cast('int', src['size'])), names))
    return ans


def download_size(lang: str | None) -> int:
    """The number of bytes that need to be downloaded before the language can be checked"""
    return sum(s.size for s in pending_downloads(lang))


def is_language_data_downloaded(lang: str | None) -> bool:
    """True if checking the language needs no downloads. Raises UnsupportedRulesLanguage for unsupported languages."""
    from langtool import dictionaries

    get_langtool()
    return bool(dictionaries.is_available(resource_language(code_for(lang))))


def download_language_data(lang: str | None, progress: Callable[[int, int], None] | None = None, abort: Event | None = None) -> None:
    """
    Download the data needed to check the language. progress is called with
    (bytes received, total bytes to download). Raises DownloadAborted if abort
    is set during the download.
    """
    lt = get_langtool()
    code = code_for(lang)
    total = download_size(lang)
    file_sizes: dict[str, int] = {}

    def on_progress(url: str, received: int, file_total: int) -> None:
        if abort is not None and abort.is_set():
            # langtool removes the partially downloaded file when the callback raises
            raise DownloadAborted(f'Download of {url} was aborted')
        file_sizes[url] = received
        if progress is not None:
            progress(min(total, sum(file_sizes.values())), total)

    lt.download_dictionaries(code, progress=on_progress)


# }}}


def make_issue(m: LTMatch) -> Issue:
    return Issue(
        m.offset,
        m.offset + m.length,
        tuple(m.replacements),
        m.message,
        m.short_message or '',
        m.rule_id,
        m.category or '',
        (m.issue_type or 'uncategorized').lower(),
        m.url or '',
    )


def sentence_spans(sentences: Sequence[str]) -> list[tuple[int, int]]:
    """Convert consecutive pieces of a text into (start, end) offsets, excluding surrounding whitespace"""
    ans = []
    pos = 0
    for s in sentences:
        stripped = s.strip()
        if stripped:
            start = pos + len(s) - len(s.lstrip())
            ans.append((start, start + len(stripped)))
        pos += len(s)
    return ans


class RuleChecker:
    """Check text with the rules of LanguageTool. Safe to use from multiple threads."""

    def __init__(self) -> None:
        self.tools: OrderedDict[tuple[str, RuleOptions], LTTool] = OrderedDict()
        self.lock = Lock()

    def tool(self, lang: str | None, options: RuleOptions = DEFAULT_RULE_OPTIONS) -> LTTool:
        code = code_for(lang)
        options = options.normalized()
        key = code, options
        with self.lock:
            if (t := self.tools.get(key)) is None:
                t = self.tools[key] = self.create_tool(code, options)
                while len(self.tools) > MAX_CACHED_TOOLS:
                    self.tools.popitem(last=False)
            else:
                self.tools.move_to_end(key)
            return t

    def create_tool(self, code: str, options: RuleOptions) -> LTTool:
        lt = get_langtool()
        t = cast('LTTool', lt.LanguageTool(code, download=False, picky=options.picky, spell_check=False))
        # Rules are enabled first so that disabling a category overrides enabling a rule in it
        for rule_id in options.enabled_rules:
            t.enable_rule(rule_id)
        if options.disabled_rules:
            t.disable_rules(options.disabled_rules)
        for category in options.disabled_categories:
            t.disable_category(category)
        return t

    def call[T](self, code: str, f: Callable[[], T]) -> T:
        from langtool import DictionaryNotFound

        try:
            return f()
        except DictionaryNotFound:
            raise LanguageDataNotDownloaded(code) from None

    def check(self, text: str, lang: str | None = None, options: RuleOptions = DEFAULT_RULE_OPTIONS) -> list[Issue]:
        """Return the issues in text, which should be a paragraph or less, sorted by position"""
        t = self.tool(lang, options)
        return [make_issue(m) for m in self.call(code_for(lang), lambda: t.check(text))]

    def sentences(self, text: str, lang: str | None = None) -> list[tuple[int, int]]:
        """Split text into sentences, returning their (start, end) offsets without surrounding whitespace"""
        t = self.tool(lang)
        return sentence_spans(self.call(code_for(lang), lambda: t.sentences(text)))
