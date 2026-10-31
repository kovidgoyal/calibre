#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Grammar checking that combines the rules of LanguageTool, which support many
# languages, are fast and come with explanations of the issues they find,
# with the neural network models, which support only English:
#
# * Paragraphs are checked with the rules and split into sentences by
#   langtool.
# * When an issue found by the rules has several possible replacements, they
#   are ranked by the checking model, if it has been downloaded.
# * Optionally (the deep check), every sentence is also checked by the
#   checking model, which finds errors the rules miss. A correction by the
#   model of exactly the text of an issue found by the rules is added to the
#   replacements for that issue. Other corrections that overlap issues found
#   by the rules are dropped, as the issues found by the rules come with
#   explanations.
# * Suggestions for rewriting a sentence that introduce new issues found by
#   the rules are dropped.

import sys
from collections import Counter
from collections.abc import Callable, Sequence
from typing import NamedTuple

from calibre.utils.grammar.backend import DEFAULT_ERROR_THRESHOLD, HAS_WORD, Backend, Edit, ModelNotDownloaded, Suggestion, overlaps
from calibre.utils.grammar.models import default_model
from calibre.utils.grammar.rules import (
    DEFAULT_RULE_OPTIONS,
    Issue,
    LanguageDataNotDownloaded,
    RuleChecker,
    RuleOptions,
    UnsupportedRulesLanguage,
    is_language_data_downloaded,
)
from calibre.utils.localization import _

# Increment when changes to this module change the results of checks, so that
# cached results are discarded
CHECKER_VERSION = 1
# Only this many of the replacements for an issue are ranked, the rest are
# left in the order the rules give them
MAX_RANKED_REPLACEMENTS = 8
MODEL_RULE_ID = 'NEURAL_NETWORK'
MODEL_CATEGORY = 'NEURAL_NETWORK'


class CheckOptions(NamedTuple):
    rules: RuleOptions = DEFAULT_RULE_OPTIONS
    # Also check every sentence with the checking model, if there is one for the language
    deep: bool = False
    # Rank the replacements for issues with the checking model, if it has been downloaded
    rank: bool = True
    # See Backend.check_sentences()
    error_threshold: float = DEFAULT_ERROR_THRESHOLD


DEFAULT_CHECK_OPTIONS = CheckOptions()


class ParagraphResult(NamedTuple):
    text: str
    # The (start, end) offsets of the sentences in text
    sentences: tuple[tuple[int, int], ...]
    # Sorted by position
    issues: tuple[Issue, ...]
    # Whether the checking model was used for a deep check and for ranking
    # replacements
    deep_checked: bool = False
    ranked: bool = False


def containing_sentence(sentences: Sequence[tuple[int, int]], start: int, end: int) -> tuple[int, int] | None:
    for s, e in sentences:
        if s <= start and end <= e:
            return s, e
    return None


def sort_issues(issues: list[Issue]) -> tuple[Issue, ...]:
    return tuple(sorted(issues, key=lambda i: (i.start, i.end)))


def model_issue(start: int, end: int, replacement: str) -> Issue:
    return Issue(start, end, (replacement,), _('Possible error, found by the neural network'), '', MODEL_RULE_ID, MODEL_CATEGORY, 'grammar', '', 'model')


class Checker:
    """
    Check paragraphs for grammar, style and typography issues and generate
    suggestions for improving sentences. Raises LanguageDataNotDownloaded if
    the data for checking the language has not been downloaded and
    UnsupportedRulesLanguage if the language is not supported. Safe to use
    from multiple threads.
    """

    def __init__(self, backend: Backend | None = None, rules: RuleChecker | None = None) -> None:
        self.backend = backend if backend is not None else Backend()
        self.rules = rules if rules is not None else RuleChecker()

    def missing_model(self, lang: str | None) -> ModelNotDownloaded | None:
        """Return the error for the checking model for the language not being downloaded, if it is not"""
        if model_id := default_model('check', lang):
            try:
                self.backend.load(model_id)
            except ModelNotDownloaded as e:
                return e
        return None

    def ranking_model(self, lang: str | None) -> str:
        """The id of the model to use for ranking replacements or the empty string if there is no usable model"""
        if not (model_id := default_model('check', lang)):
            return ''
        try:
            self.backend.load(model_id)
        except ModelNotDownloaded:
            return ''
        except (OSError, RuntimeError) as e:
            # Failing to rank replacements is not worth failing the check for
            print(f'Failed to load the grammar model {model_id} with error: {e}', file=sys.stderr)
            return ''
        return model_id

    def check_paragraphs(self, paragraphs: Sequence[str], lang: str | None = None, options: CheckOptions = DEFAULT_CHECK_OPTIONS) -> list[ParagraphResult]:
        deep_model = ''
        if options.deep and (model_id := default_model('check', lang)) and self.missing_model(lang) is None:
            deep_model = model_id
        rank_model = self.ranking_model(lang) if options.rank else ''
        return [self.check_paragraph(p, lang, options, deep_model, rank_model) for p in paragraphs]

    def check_paragraph(self, text: str, lang: str | None, options: CheckOptions, deep_model: str, rank_model: str) -> ParagraphResult:
        deep, ranked = bool(deep_model), bool(rank_model)
        if not HAS_WORD.search(text):
            return ParagraphResult(text, (), (), deep, ranked)
        issues = self.rules.check(text, lang, options.rules)
        sentences = self.rules.sentences(text, lang)
        if rank_model:
            issues = self.rank_replacements(text, sentences, issues, lang, rank_model)
        if deep_model:
            issues = self.add_model_issues(text, sentences, issues, lang, deep_model, options.error_threshold)
        return ParagraphResult(text, tuple(sentences), sort_issues(issues), deep, ranked)

    def rank_replacements(self, text: str, sentences: Sequence[tuple[int, int]], issues: list[Issue], lang: str | None, model_id: str) -> list[Issue]:
        ans = []
        for issue in issues:
            span = containing_sentence(sentences, issue.start, issue.end)
            if len(issue.replacements) < 2 or span is None:
                ans.append(issue)
                continue
            s, e = span
            sentence = text[s:e]
            a, b = issue.start - s, issue.end - s
            head = issue.replacements[:MAX_RANKED_REPLACEMENTS]
            scores = self.backend.score_corrections(sentence, [sentence[:a] + r + sentence[b:] for r in head], lang, model_id)
            # Replacements that could not be scored go last, ties keep the order given by the rules
            order = sorted(range(len(head)), key=lambda i: (scores[i] is None, -(scores[i] or 0.0)))
            ans.append(issue._replace(replacements=tuple(head[i] for i in order) + issue.replacements[MAX_RANKED_REPLACEMENTS:]))
        return ans

    def add_model_issues(
        self, text: str, sentences: Sequence[tuple[int, int]], issues: list[Issue], lang: str | None, model_id: str, error_threshold: float
    ) -> list[Issue]:
        ans = list(issues)
        rule_spans = [(i.start, i.end) for i in issues]
        results = self.backend.check_sentences([text[s:e] for s, e in sentences], lang, model_id, error_threshold)
        for (s, e), r in zip(sentences, results):
            for edit in r.edits:
                start, end = edit.start + s, edit.end + s
                same = next((i for i, x in enumerate(ans) if x.source == 'rules' and x.start == start and x.end == end), -1)
                if same > -1:
                    x = ans[same]
                    if edit.replacement not in x.replacements:
                        ans[same] = x._replace(replacements=(edit.replacement, *x.replacements))
                elif not overlaps(Edit(start, end, edit.replacement), rule_spans):
                    ans.append(model_issue(start, end, edit.replacement))
        return ans

    def suggest(
        self,
        sentence: str,
        lang: str | None = None,
        kinds: Sequence[str] = (),
        count: int = 1,
        num_beams: int = 1,
        model_id: str = '',
        should_abort: Callable[[], bool] | None = None,
    ) -> list[Suggestion]:
        """See Backend.suggest(). Suggestions that introduce issues found by the rules are omitted."""
        suggestions = self.backend.suggest(sentence, lang, kinds, count, num_beams, model_id, should_abort)
        if not suggestions:
            return suggestions
        try:
            if not is_language_data_downloaded(lang):
                return suggestions
            before = Counter(i.rule_id for i in self.rules.check(sentence, lang))
            return [s for s in suggestions if not Counter(i.rule_id for i in self.rules.check(s.text, lang)) - before]
        except UnsupportedRulesLanguage, LanguageDataNotDownloaded:
            return suggestions

    def abort(self) -> None:
        self.backend.abort()


def develop() -> None:
    import time

    c = Checker(Backend(gpu_mode='off'))
    paragraphs = sys.argv[1:] or [
        'She go to school yesterday and buyed three apple. Their going to the store tomorrow, isn’t it?',
        '“What do you mean?” asked Elizabeth, her eyes wide with astonishment. Despite of the rain, we goes outside.',
        'He said that, he would come. I has a idea.',
    ]
    for deep in (False, True):
        st = time.perf_counter()
        for r in c.check_paragraphs(paragraphs, 'en', CheckOptions(deep=deep)):
            print(r.text, f'(deep: {r.deep_checked}, ranked: {r.ranked})')
            for i in r.issues:
                print(f'    {r.text[i.start : i.end]!r} -> {list(i.replacements[:4])} [{i.source}:{i.rule_id}] {i.message}')
        print(f'Checked {len(paragraphs)} paragraphs with deep={deep} in {time.perf_counter() - st:.2f} seconds\n')
