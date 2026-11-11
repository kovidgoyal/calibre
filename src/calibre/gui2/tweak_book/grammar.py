#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Grammar checking in the editor: underlining of the issues found in the file
# being edited, correcting them from the context menu, the Check grammar tool
# that lists the issues found in the whole book, and suggestions for rewriting
# sentences.

import sys
import traceback
from functools import partial
from itertools import count
from threading import Event, Thread
from typing import TYPE_CHECKING, Literal, NamedTuple

from qt.core import (
    QAbstractItemView,
    QAbstractTableModel,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHideEvent,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QShowEvent,
    QSize,
    QSplitter,
    Qt,
    QTableView,
    QTextBrowser,
    QTextCursor,
    QTextEdit,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre import human_readable, prepare_string_for_xml
from calibre.ebooks.chardet import replace_encoding_declarations
from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.gui2 import error_dialog, open_url, question_dialog
from calibre.gui2.tweak_book import current_container, dictionaries, tprefs
from calibre.gui2.tweak_book.editor.themes import theme_format
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import FlowLayout
from calibre.utils.grammar.backend import Suggestion, variants_to_download
from calibre.utils.grammar.checker import MODEL_RULE_ID, CheckOptions, containing_sentence
from calibre.utils.grammar.document import (
    IgnoreKey,
    ParagraphRef,
    SentenceRef,
    Utf16Map,
    apply_suggestion,
    can_apply_suggestion,
    correct_source,
    correction_edits,
    ignore_key,
    issue_source_ranges,
    paragraph_refs,
    paragraphs_by_language,
    relocate,
    sentence_at,
    simple_sentences,
    suggestion_edits,
)
from calibre.utils.grammar.gpu import GpuMode, gpu_mode_from_string
from calibre.utils.grammar.markup import EditNotPossible, Paragraph, SourceEdit, extract_paragraphs, visible_issues
from calibre.utils.grammar.models import DownloadAborted, Task, Variant, default_model, download_size, files_to_download, is_downloaded, is_usable
from calibre.utils.grammar.rules import RuleOptions
from calibre.utils.grammar.worker import CheckResponse, SuggestResponse
from calibre.utils.icu import primary_contains, primary_sort_key
from calibre.utils.localization import _, calibre_langcode_to_name, canonicalize_lang, lang_as_iso639_1

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from calibre.ebooks.oeb.polish.container import Container
    from calibre.gui2.tweak_book.editor.text import TextEdit
    from calibre.utils.grammar.backend import Edit
    from calibre.utils.grammar.cache import ResultCache
    from calibre.utils.grammar.checker import ParagraphResult
    from calibre.utils.grammar.rules import Issue
    from calibre.utils.grammar.worker import GrammarCheckWorker, SuggestionWorker

# The delay after the last edit before the file being edited is checked again
INLINE_CHECK_DELAY = 1000
MAX_CONTEXT_MENU_REPLACEMENTS = 7
# The delay after the cursor stops moving before suggestions for rewriting the sentence it is in are generated
SUGGESTION_DELAY = 750
SUGGESTIONS_PER_KIND = 1
DEFAULT_SUGGESTION_KINDS = ('grammar', 'fluency', 'clarity')
LanguageStatus = Literal['ready', 'missing', 'unsupported']


# Settings {{{


def disabled_rules() -> dict[str, str]:
    """Map the ids of the rules the user has disabled to a description of them"""
    ans = tprefs['grammar_disabled_rules']
    return ans if isinstance(ans, dict) else {}


def check_options() -> CheckOptions:
    rules = tuple(x for x in disabled_rules() if x != MODEL_RULE_ID)
    return CheckOptions(rules=RuleOptions(disabled_rules=rules, picky=bool(tprefs['grammar_picky'])), deep=bool(tprefs['grammar_deep_check']))


def gpu_mode() -> GpuMode:
    return gpu_mode_from_string(tprefs['grammar_gpu_mode'])


def book_language() -> str:
    """The language of the book, used for text that has no language specified in the HTML"""
    loc = dictionaries.default_locale
    lc = lang_as_iso639_1(loc.langcode) or loc.langcode
    return f'{lc}-{loc.countrycode}' if loc.countrycode else lc


def language_name(lang: str) -> str:
    return calibre_langcode_to_name(canonicalize_lang(lang) or lang)


def is_shown(issue: Issue, key: IgnoreKey, service: GrammarService) -> bool:
    return key not in service.ignored and issue.rule_id not in disabled_rules()


def rule_description(issue: Issue) -> str:
    return issue.short_message or issue.message


# }}}


# Service {{{


class Receiver(NamedTuple):
    # The object that made the request, responses are not delivered once it is deleted
    owner: QObject
    callback: Callable[[CheckResponse], None]


class SuggestionReceiver(NamedTuple):
    owner: QObject
    callback: Callable[[SuggestResponse], None]


class GrammarService(QObject):
    """
    Runs grammar checks for the inline checkers in the editors and the Check
    grammar tool, in a single worker process, and generates suggestions for
    rewriting sentences in another, with a shared cache of results. Responses
    are delivered in the GUI thread.
    """

    response_received = pyqtSignal(int, object)
    suggestion_received = pyqtSignal(int, object)
    # Emitted when the options for checking change, so all text must be checked again
    options_changed = pyqtSignal()
    # Emitted when the set of ignored issues changes
    ignored_changed = pyqtSignal()
    # Emitted the first time in a session that text in a language whose data
    # has not been downloaded is checked
    language_data_needed = pyqtSignal(str)
    language_data_downloaded = pyqtSignal(str)
    # Emitted when an inline check fails, with the error and details
    inline_check_failed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.worker: GrammarCheckWorker | None = None
        self.suggestion_worker: SuggestionWorker | None = None
        self.cache: ResultCache | None = None
        self.callbacks: dict[int, Receiver] = {}
        self.request_ids: dict[int, int] = {}
        self.suggestion_callbacks: dict[int, SuggestionReceiver] = {}
        self.suggestion_request_ids: dict[int, int] = {}
        # Set on shutdown, after which no new requests are made, so that no
        # worker processes are started while the application exits
        self.closed = False
        self.tokens = count(1)
        self.ignored: set[IgnoreKey] = set()
        self.language_status_cache: dict[str, LanguageStatus] = {}
        self.reported_missing_data: set[str] = set()
        self.reported_inline_errors: set[str] = set()
        self.response_received.connect(self.dispatch, type=Qt.ConnectionType.QueuedConnection)
        self.suggestion_received.connect(self.dispatch_suggestion, type=Qt.ConnectionType.QueuedConnection)

    def result_cache(self) -> ResultCache:
        if self.cache is None:
            from calibre.utils.grammar.cache import ResultCache

            self.cache = ResultCache('')
        return self.cache

    def ensure_worker(self) -> GrammarCheckWorker:
        if self.worker is None:
            from calibre.utils.grammar.worker import GrammarCheckWorker

            self.worker = GrammarCheckWorker(gpu_mode=gpu_mode(), cache=self.result_cache())
        return self.worker

    def ensure_suggestion_worker(self) -> SuggestionWorker:
        if self.suggestion_worker is None:
            from calibre.utils.grammar.worker import SuggestionWorker

            self.suggestion_worker = SuggestionWorker(gpu_mode=gpu_mode(), cache=self.result_cache())
        return self.suggestion_worker

    def language_status(self, lang: str) -> LanguageStatus:
        if (ans := self.language_status_cache.get(lang)) is not None:
            return ans
        try:
            from calibre.utils.grammar.rules import UnsupportedRulesLanguage, is_language_data_downloaded

            try:
                ans = 'ready' if is_language_data_downloaded(lang) else 'missing'
            except UnsupportedRulesLanguage:
                ans = 'unsupported'
        except ImportError as e:
            print(f'Grammar checking is not available as langtool could not be loaded with error: {e}', file=sys.stderr)
            ans = 'unsupported'
        self.language_status_cache[lang] = ans
        if ans == 'missing':
            self.report_missing_data(lang)
        return ans

    def report_missing_data(self, lang: str) -> None:
        if lang not in self.reported_missing_data:
            self.reported_missing_data.add(lang)
            self.language_data_needed.emit(lang)

    def did_download_language_data(self, lang: str) -> None:
        self.language_status_cache.clear()
        self.language_data_downloaded.emit(lang)

    def check(self, owner: QObject, paragraphs: Sequence[str], lang: str, callback: Callable[[CheckResponse], None]) -> int:
        """
        Check the paragraphs, returning a token that identifies the request.
        callback is called in the GUI thread with the responses, the last one
        having done=True, unless owner is deleted, the request is cancelled
        first or the service has been shut down.
        """
        token = next(self.tokens)
        if self.closed:
            return token
        self.callbacks[token] = Receiver(owner, callback)

        def relay(r: CheckResponse) -> None:
            # Called from a worker thread or, for cached results, this thread
            self.response_received.emit(token, r)

        try:
            self.request_ids[token] = self.ensure_worker().check(paragraphs, relay, lang, check_options())
        except Exception as e:
            relay(CheckResponse(-1, {}, done=True, error=str(e) or e.__class__.__name__, details=traceback.format_exc()))
        return token

    def suggest(self, owner: QObject, sentence: str, lang: str, kind: str, callback: Callable[[SuggestResponse], None]) -> int:
        """
        Generate suggestions of the specified kind for rewriting the sentence,
        returning a token that identifies the request. callback is called in the
        GUI thread with the responses, the last one having done=True, unless
        owner is deleted or the request is cancelled first.
        """
        token = next(self.tokens)
        if self.closed:
            return token
        self.suggestion_callbacks[token] = SuggestionReceiver(owner, callback)

        def relay(r: SuggestResponse) -> None:
            self.suggestion_received.emit(token, r)

        try:
            self.suggestion_request_ids[token] = self.ensure_suggestion_worker().suggest(
                sentence, relay, lang, kinds=(kind,), count=SUGGESTIONS_PER_KIND, num_beams=1, cancel_previous=False
            )
        except Exception as e:
            relay(SuggestResponse(-1, (), done=True, error=str(e) or e.__class__.__name__, details=traceback.format_exc()))
        return token

    def dispatch_suggestion(self, token: int, r: SuggestResponse) -> None:
        receiver = self.suggestion_callbacks.get(token)
        if r.done:
            self.suggestion_callbacks.pop(token, None)
            self.suggestion_request_ids.pop(token, None)
        if receiver is not None and not sip.isdeleted(receiver.owner):
            receiver.callback(r)

    def cancel_suggestion(self, token: int) -> None:
        self.suggestion_callbacks.pop(token, None)
        request_id = self.suggestion_request_ids.pop(token, None)
        if request_id is not None and self.suggestion_worker is not None:
            self.suggestion_worker.cancel(request_id)

    def dispatch(self, token: int, r: CheckResponse) -> None:
        receiver = self.callbacks.get(token)
        if r.done:
            self.callbacks.pop(token, None)
            self.request_ids.pop(token, None)
        if r.language_data:
            self.language_status_cache.clear()
        if receiver is not None and not sip.isdeleted(receiver.owner):
            receiver.callback(r)

    def cancel(self, token: int) -> None:
        self.callbacks.pop(token, None)
        request_id = self.request_ids.pop(token, None)
        if request_id is not None and self.worker is not None:
            self.worker.cancel(request_id)

    def clear_ignored(self) -> None:
        if self.ignored:
            self.ignored.clear()
            self.ignored_changed.emit()

    def ignore(self, key: IgnoreKey) -> None:
        self.ignored.add(key)
        self.ignored_changed.emit()

    def disable_rule(self, rule_id: str, description: str) -> None:
        rules = dict(disabled_rules())
        rules[rule_id] = description
        tprefs['grammar_disabled_rules'] = rules
        self.options_changed.emit()

    def set_disabled_rules(self, rules: dict[str, str]) -> None:
        if rules != disabled_rules():
            tprefs['grammar_disabled_rules'] = rules
            self.options_changed.emit()

    def shutdown_workers(self) -> None:
        self.callbacks.clear()
        self.request_ids.clear()
        self.suggestion_callbacks.clear()
        self.suggestion_request_ids.clear()
        if self.worker is not None:
            self.worker.shutdown()
            self.worker = None
        if self.suggestion_worker is not None:
            self.suggestion_worker.shutdown()
            self.suggestion_worker = None

    def gpu_mode_changed(self) -> None:
        # The workers use the GPU mode they were started with
        self.shutdown_workers()
        self.options_changed.emit()

    def shutdown(self) -> None:
        self.closed = True
        self.shutdown_workers()
        if self.cache is not None:
            self.cache.close()
            self.cache = None


_service: GrammarService | None = None


def grammar_service() -> GrammarService:
    global _service
    if _service is None:
        _service = GrammarService()
    return _service


def shutdown_grammar_service() -> None:
    global _service
    if _service is not None:
        _service.shutdown()
        _service = None


# }}}


# Downloads {{{


class LanguageDataDownload(QProgressDialog):
    progress_received = pyqtSignal(int, int)
    download_finished = pyqtSignal(str, str)

    def __init__(self, lang: str, parent: QWidget | None = None) -> None:
        super().__init__(_('Downloading the data for checking {}...').format(language_name(lang)), _('&Cancel'), 0, 0, parent)
        self.setWindowTitle(_('Downloading grammar data'))
        self.setMinimumDuration(0)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.lang = lang
        self.error = self.details = ''
        self.succeeded = False
        self.abort = Event()
        self.canceled.connect(self.abort.set)
        self.progress_received.connect(self.on_progress, type=Qt.ConnectionType.QueuedConnection)
        self.download_finished.connect(self.on_finished, type=Qt.ConnectionType.QueuedConnection)
        self.download_thread = Thread(target=self.run, name='GrammarDataDownload', daemon=True)
        self.download_thread.start()

    def run(self) -> None:
        from calibre.utils.grammar.rules import download_language_data

        try:
            download_language_data(self.lang, self.progress_received.emit, self.abort)
        except DownloadAborted:
            self.download_finished.emit('', 'aborted')
        except Exception as e:
            self.download_finished.emit(str(e) or e.__class__.__name__, traceback.format_exc())
        else:
            self.download_finished.emit('', '')

    def on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.setMaximum(1000)
            self.setValue(min(1000, int(1000 * received / total)))

    def on_finished(self, error: str, details: str) -> None:
        self.error, self.details = error, details
        self.succeeded = not error and details != 'aborted'
        if self.succeeded:
            self.accept()
        else:
            self.reject()


def ensure_language_data(parent: QWidget | None, lang: str) -> bool:
    """Download the data for checking the language, if needed, asking the user first. Returns True if the language can be checked."""
    from calibre.utils.grammar.rules import UnsupportedRulesLanguage, download_size, is_language_data_downloaded

    service = grammar_service()
    try:
        if is_language_data_downloaded(lang):
            return True
        size = download_size(lang)
    except UnsupportedRulesLanguage:
        error_dialog(parent, _('Language not supported'), _('Checking the grammar of {} is not supported').format(language_name(lang)), show=True)
        return False
    except Exception as e:
        error_dialog(
            parent,
            _('Grammar checking not available'),
            _('Failed to load the grammar checker with error: {}').format(e),
            det_msg=traceback.format_exc(),
            show=True,
        )
        return False
    if not question_dialog(
        parent,
        _('Download grammar data?'),
        _('Checking the grammar of {0} requires downloading {1} of data. Download it now?').format(language_name(lang), human_readable(size)),
    ):
        return False
    d = LanguageDataDownload(lang, parent)
    d.exec()
    if d.error:
        error_dialog(
            parent,
            _('Download failed'),
            _('Failed to download the data for checking {0} with error: {1}').format(language_name(lang), d.error),
            det_msg=d.details,
            show=True,
        )
    if d.succeeded:
        service.did_download_language_data(lang)
    return d.succeeded


def as_variant(x: str) -> Variant | None:
    if x == 'cpu':
        return 'cpu'
    if x == 'gpu':
        return 'gpu'
    return None


def model_description(task: Task) -> str:
    if task == 'check':
        return _('the neural network used for deep grammar checks')
    return _('the neural network used for suggesting rewrites of sentences')


def ensure_model(parent: QWidget | None, task: Task, lang: str, variants: Sequence[Variant] = (), model_id: str = '') -> bool:
    """
    Download the model for the task and language, or the specified model, if
    needed, asking the user first. If variants is empty, nothing is downloaded
    if some variant of the model is usable, otherwise the variants for the GPU
    mode are downloaded. Returns True if the model is available.
    """
    from calibre.gui2.tts.download import download_resources

    model_id = model_id or default_model(task, lang) or ''
    if not model_id:
        error_dialog(parent, _('Language not supported'), _('This is not available for {}').format(language_name(lang)), show=True)
        return False
    if not variants:
        if is_usable(model_id):
            return True
        variants = variants_to_download(model_id, gpu_mode())
    missing = [v for v in variants if not is_downloaded(model_id, v)]
    if not missing:
        return True
    urls: dict[str, tuple[str, str]] = {}
    hashes: dict[str, str] = {}
    try:
        for v in missing:
            u, h = files_to_download(model_id, v)
            urls.update(u), hashes.update(h)
    except OSError as e:
        error_dialog(parent, _('Download failed'), _('Failed to prepare for downloading the neural network with error: {}').format(e), show=True)
        return False
    what = model_description(task)
    size = human_readable(sum(download_size(model_id, v) for v in missing))
    msg = _('This requires downloading {0} ({1}). It only needs to be downloaded once.').format(what, size)
    if len(missing) > 1:
        msg += ' ' + _('Versions for both the CPU and the GPU are downloaded, the faster one is used.')
    if not question_dialog(parent, _('Download neural network?'), msg + '<p>' + _('Download it now?')):
        return False
    return download_resources(_('Downloading neural network'), _('Downloading {}').format(what), urls, parent=parent, hashes=hashes)


# }}}


# Inline checking {{{


class InlineIssue(NamedTuple):
    ref: ParagraphRef
    issue: Issue
    key: IgnoreKey
    # Cursors selecting the marked text, they track edits to the document
    cursors: tuple[QTextCursor, ...]

    @property
    def start(self) -> int:
        return min(c.selectionStart() for c in self.cursors)

    @property
    def end(self) -> int:
        return max(c.selectionEnd() for c in self.cursors)

    def contains(self, pos: int) -> bool:
        return any(c.selectionStart() <= pos < c.selectionEnd() for c in self.cursors)


class ParseCache(NamedTuple):
    text_version: int
    default_lang: str
    paragraphs: list[Paragraph]
    refs: list[ParagraphRef]


class InlineGrammarChecker(QObject):
    """Checks the grammar of the HTML file being edited, underlining the issues found"""

    def __init__(self, editor: TextEdit) -> None:
        super().__init__(editor)
        self.editor = editor
        self.service = grammar_service()
        self.timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(INLINE_CHECK_DELAY), t.timeout.connect(self.check)
        # Incremented on every change to the text
        self.text_version = 0
        # The text version, language and paragraphs of the latest check
        self.checked_version = -1
        self.default_lang = ''
        self.paragraphs: list[Paragraph] = []
        self.refs: list[ParagraphRef] = []
        self.results: dict[int, ParagraphResult] = {}
        self.generation = 0
        self.shown_generation = -1
        self.tokens: list[int] = []
        self.outstanding = 0
        self.issues: list[InlineIssue] = []
        # The paragraphs of the text, when it has not been checked, see current_paragraphs()
        self.parse_cache: ParseCache | None = None
        # Languages of text in the file that cannot be checked as their data has not been downloaded
        self.missing_languages: set[str] = set()
        doc = editor.document()
        assert doc is not None
        # contentsChange is also emitted when the syntax highlighter changes
        # formatting, contentsChanged only when the text changes
        doc.contentsChanged.connect(self.contents_changed)
        self.service.options_changed.connect(self.recheck)
        self.service.language_data_downloaded.connect(self.recheck)
        self.service.ignored_changed.connect(self.show_results)

    @property
    def enabled(self) -> bool:
        return bool(tprefs['inline_grammar_check'])

    def contents_changed(self) -> None:
        self.text_version += 1
        if self.enabled:
            self.timer.start()

    def recheck(self, *a: object) -> None:
        self.checked_version = -1
        if self.enabled:
            self.timer.start()
        else:
            self.clear()

    def clear(self) -> None:
        self.cancel()
        self.timer.stop()
        self.results.clear()
        self.paragraphs, self.refs = [], []
        self.missing_languages.clear()
        self.checked_version = -1
        self.set_issues([])

    def cancel(self) -> None:
        for token in self.tokens:
            self.service.cancel(token)
        self.tokens = []
        self.outstanding = 0

    def visible_range(self) -> tuple[int, int]:
        vp = self.editor.viewport()
        assert vp is not None
        return self.editor.cursorForPosition(QPoint(0, 0)).position(), self.editor.cursorForPosition(QPoint(vp.width(), vp.height())).position()

    def check(self) -> None:
        if not self.enabled or self.checked_version == self.text_version:
            return
        self.cancel()
        self.generation += 1
        self.checked_version = self.text_version
        source = self.editor.toPlainText()
        self.default_lang = book_language()
        self.paragraphs = extract_paragraphs(source, self.default_lang)
        self.refs = paragraph_refs(self.paragraphs)
        self.results = {}
        self.missing_languages.clear()
        # Check the paragraphs that are visible first
        um = Utf16Map(source)
        vstart, vend = (um.from_utf16(x) for x in self.visible_range())

        def is_hidden(i: int) -> bool:
            s, e = self.paragraphs[i].source_span
            return e < vstart or s > vend

        groups = sorted(
            ((lang, sorted(indices, key=is_hidden)) for lang, indices in paragraphs_by_language(self.paragraphs, self.default_lang).items()),
            key=lambda x: is_hidden(x[1][0]),
        )
        for lang, indices in groups:
            status = self.service.language_status(lang)
            if status == 'missing':
                self.missing_languages.add(lang)
            if status != 'ready':
                continue
            self.outstanding += 1
            texts = [self.paragraphs[i].text for i in indices]
            self.tokens.append(self.service.check(self, texts, lang, partial(self.on_response, self.generation, tuple(indices))))
        if not self.outstanding:
            self.set_issues([])

    def on_response(self, generation: int, indices: tuple[int, ...], r: CheckResponse) -> None:
        if generation != self.generation:
            return
        for i, res in r.results.items():
            self.results[indices[i]] = res
        if r.done:
            self.outstanding -= 1
            if r.error and not r.cancelled:
                if r.language_data:
                    self.missing_languages.add(r.language_data)
                    self.service.report_missing_data(r.language_data)
                elif r.model_id:
                    # A neural network that is not downloaded, which can be
                    # downloaded from the Check grammar tool
                    pass
                elif r.error not in self.service.reported_inline_errors:
                    self.service.reported_inline_errors.add(r.error)
                    print(f'Grammar check failed with error: {r.error}\n{r.details}', file=sys.stderr)
                    self.service.inline_check_failed.emit(r.error, r.details)
        if self.checked_version != self.text_version:
            # The text has changed so the results cannot be shown, it will be checked again
            return
        # Wait for all results before replacing the issues shown from an
        # earlier check, to avoid flicker, unless there are none
        if self.outstanding < 1 or self.shown_generation == generation or not self.issues:
            self.shown_generation = generation
            self.show_results()

    def show_results(self) -> None:
        if self.checked_version != self.text_version:
            # Only remove issues that are now ignored, the rest are updated
            # when the changed text has been checked
            self.set_issues([x for x in self.issues if is_shown(x.issue, x.key, self.service)])
            return
        source_map: Utf16Map | None = None
        doc = self.editor.document()
        issues: list[InlineIssue] = []
        for idx, result in sorted(self.results.items()):
            p = self.paragraphs[idx]
            for issue in visible_issues(p, result.issues):
                key = ignore_key(result, issue)
                if not is_shown(issue, key, self.service):
                    continue
                if source_map is None:
                    source_map = Utf16Map(self.editor.toPlainText())
                cursors = []
                for s, e in issue_source_ranges(p, issue):
                    c = QTextCursor(doc)
                    c.setPosition(source_map.to_utf16(s))
                    c.setPosition(source_map.to_utf16(e), QTextCursor.MoveMode.KeepAnchor)
                    cursors.append(c)
                if cursors:
                    issues.append(InlineIssue(self.refs[idx], issue, key, tuple(cursors)))
        self.set_issues(issues)

    def set_issues(self, issues: list[InlineIssue]) -> None:
        self.issues = issues
        self.update_selections()

    def update_selections(self) -> None:
        fmt = theme_format(self.editor.theme, 'GrammarError')
        sels = []
        for x in self.issues:
            for c in x.cursors:
                sel = QTextEdit.ExtraSelection()
                sel.cursor = c
                sel.format = fmt
                sels.append(sel)
        self.editor.grammar_selections = sels
        self.editor.update_extra_selections()

    def issue_at(self, pos: int) -> InlineIssue | None:
        return next((x for x in self.issues if x.contains(pos)), None)

    def remove_issue(self, issue: InlineIssue) -> None:
        self.set_issues([x for x in self.issues if x is not issue])

    def apply_replacement(self, issue: InlineIssue, replacement: str) -> bool:
        source = self.editor.toPlainText()
        try:
            edits = correction_edits(source, self.default_lang, issue.ref, issue.issue, replacement)
        except EditNotPossible as e:
            error_dialog(
                self.editor,
                _('Cannot correct'),
                _('Cannot make this correction, as the text has changed since it was checked or contains text that must not be changed.'),
                det_msg=str(e),
                show=True,
            )
            return False
        self.apply_source_edits(source, edits)
        self.remove_issue(issue)
        return True

    def apply_source_edits(self, source: str, edits: Sequence[SourceEdit]) -> None:
        """Apply the edits of the source, which must be the current text of the document, as a single undo step"""
        um = Utf16Map(source)
        c = QTextCursor(self.editor.document())
        c.beginEditBlock()
        for e in reversed(edits):
            c.setPosition(um.to_utf16(e.start))
            c.setPosition(um.to_utf16(e.end), QTextCursor.MoveMode.KeepAnchor)
            c.insertText(e.replacement)
        c.endEditBlock()

    def current_paragraphs(self, source: str) -> tuple[list[Paragraph], list[ParagraphRef], dict[int, ParagraphResult], str]:
        """The paragraphs of the current text, their refs, check results and the default language, cached until the text changes"""
        if self.checked_version == self.text_version and self.paragraphs:
            return self.paragraphs, self.refs, self.results, self.default_lang
        default_lang = book_language()
        if self.parse_cache is None or self.parse_cache.text_version != self.text_version or self.parse_cache.default_lang != default_lang:
            paragraphs = extract_paragraphs(source, default_lang)
            self.parse_cache = ParseCache(self.text_version, default_lang, paragraphs, paragraph_refs(paragraphs))
        return self.parse_cache.paragraphs, self.parse_cache.refs, {}, default_lang

    def sentence_target(self, pos: int) -> SentenceTarget | None:
        """The sentence at the specified position in the document, or None if there is no sentence there"""
        source = self.editor.toPlainText()
        paragraphs, refs, results, default_lang = self.current_paragraphs(source)
        sentence = sentence_at(paragraphs, refs, results, Utf16Map(source).from_utf16(pos), default_lang)
        if sentence is None or (p := relocate(paragraphs, sentence.paragraph)) is None:
            return None
        return SentenceTarget(sentence, p, default_lang)

    def apply_suggestion(self, target: SentenceTarget, suggestion: Suggestion) -> bool:
        source = self.editor.toPlainText()
        try:
            edits = suggestion_edits(source, target.default_lang, target.sentence, suggestion.edits)
        except EditNotPossible as e:
            error_dialog(
                self.editor,
                _('Cannot change sentence'),
                _('Cannot rewrite the sentence, as the text has changed since the suggestion was made.'),
                det_msg=str(e),
                show=True,
            )
            return False
        self.apply_source_edits(source, edits)
        return True

    def select_next(self) -> bool:
        if not self.issues:
            return False
        pos = self.editor.textCursor().position()
        ordered = sorted(self.issues, key=lambda x: x.start)
        x = next((x for x in ordered if x.start > pos), ordered[0])
        c = self.editor.textCursor()
        c.setPosition(x.start)
        c.setPosition(x.end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(c)
        self.editor.centerCursor()
        return True

    def tooltip(self, pos: int) -> str:
        if (x := self.issue_at(pos)) is None:
            return ''
        return issue_html(x.issue)


def issue_html(issue: Issue) -> str:
    ans = f'<p>{prepare_string_for_xml(issue.message)}'
    if issue.replacements:
        ans += '<p>' + _('Suggestions:') + ' ' + ', '.join(f'<b>{prepare_string_for_xml(r)}</b>' for r in issue.replacements[:MAX_CONTEXT_MENU_REPLACEMENTS])
    return ans


def select_issue_in_editor(editor: TextEdit, default_lang: str, ref: ParagraphRef, issue: Issue) -> bool:
    """Select the text of the issue in the editor, returning False if it no longer exists"""
    source = editor.toPlainText()
    p = relocate(extract_paragraphs(source, default_lang), ref)
    if p is None:
        return False
    ranges = issue_source_ranges(p, issue)
    if not ranges:
        return False
    um = Utf16Map(source)
    c = editor.textCursor()
    c.setPosition(um.to_utf16(ranges[0][0]))
    c.setPosition(um.to_utf16(ranges[-1][1]), QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(c)
    editor.centerCursor()
    return True


# }}}


# Rewrite suggestions {{{


class SentenceTarget(NamedTuple):
    # A sentence to suggest rewrites for
    sentence: SentenceRef
    # Its paragraph, in the source at the time the sentence was found
    paragraph: Paragraph
    # The language used for text without a specified language when the source was split into paragraphs
    default_lang: str


def kind_name(kind: str) -> str:
    return {
        'grammar': _('Grammar'),
        'fluency': _('Fluency'),
        'clarity': _('Clarity'),
        'simplify': _('Simpler'),
        'formal': _('Formal'),
        'paraphrase': _('Paraphrase'),
    }.get(kind, kind.capitalize())


def available_suggestion_kinds() -> tuple[str, ...]:
    from calibre.utils.grammar.models import suggestion_kinds

    model_id = default_model('suggest', 'en')
    return suggestion_kinds(model_id) if model_id else DEFAULT_SUGGESTION_KINDS


def selected_suggestion_kinds() -> tuple[str, ...]:
    ans = tprefs['grammar_suggestion_kinds']
    if not isinstance(ans, (list, tuple)):
        return DEFAULT_SUGGESTION_KINDS
    available = available_suggestion_kinds()
    return tuple(k for k in available if k in ans)


def suggestion_html(sentence: str, edits: Sequence[Edit]) -> str:
    """The sentence with the edits shown as deleted and inserted text"""
    ans: list[str] = []
    pos = 0
    for e in sorted(edits, key=lambda e: (e.start, e.end)):
        ans.append(prepare_string_for_xml(sentence[pos : e.start]))
        if e.start < e.end:
            ans.append(f'<span style="color: #d04040; text-decoration: line-through">{prepare_string_for_xml(sentence[e.start : e.end])}</span>')
            if e.replacement:
                # Separate the deleted and inserted text, so they are readable
                ans.append('\u2009')
        if e.replacement:
            ans.append(f'<span style="color: #30a030; font-weight: bold">{prepare_string_for_xml(e.replacement)}</span>')
        pos = e.end
    ans.append(prepare_string_for_xml(sentence[pos:]))
    return ''.join(ans)


def sentence_for_issue(pf: PendingFile, x: BookIssue) -> SentenceTarget:
    p = pf.paragraphs[x.paragraph_index]
    start, end = containing_sentence(x.result.sentences or simple_sentences(x.result.text), x.issue.start, x.issue.end) or (0, len(x.result.text))
    return SentenceTarget(SentenceRef(x.ref, start, end, p.lang or x.default_lang), p, x.default_lang)


class SuggestionRow(QWidget):
    def __init__(self, sentence: str, suggestion: Suggestion, apply: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.suggestion = suggestion
        self.apply_callback = apply
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        # The apply link is inline at the end of the text, rather than a
        # button, so that the suggestion can use the full width of the panel
        self.label = la = QLabel(
            f'<b>{prepare_string_for_xml(kind_name(suggestion.kind))}:</b> {suggestion_html(sentence, suggestion.edits)}'
            f' <a href="apply:" style="text-decoration: none">{prepare_string_for_xml(_("Apply"))}</a>',
            self,
        )
        la.setWordWrap(True)
        la.setTextFormat(Qt.TextFormat.RichText)
        la.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        la.linkActivated.connect(self.link_activated)
        l.addWidget(la, stretch=1)

    def link_activated(self, link: str) -> None:
        if link == 'apply:':
            self.apply_callback()


class SuggestionsWidget(QWidget):
    """Shows suggestions for rewriting a sentence, generated in the background"""

    def __init__(self, apply: Callable[[SentenceTarget, Suggestion], bool], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.apply_callback = apply
        self.service = grammar_service()
        self.target: SentenceTarget | None = None
        self.tokens: list[int] = []
        self.pending = 0
        self.generation = 0
        self.error = ''
        # The model and variant the worker reported as not downloaded
        self.missing_model_id = ''
        self.missing_variant: Variant | None = None
        self.seen: set[str] = set()
        self.rows: list[SuggestionRow] = []
        l = QVBoxLayout(self)
        self.sentence_label = la = QLabel(self)
        la.setWordWrap(True)
        la.setTextFormat(Qt.TextFormat.RichText)
        la.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l.addWidget(la)
        kl = FlowLayout()
        l.addLayout(kl)
        selected = selected_suggestion_kinds()
        self.kind_boxes: dict[str, QCheckBox] = {}
        for kind in available_suggestion_kinds():
            cb = self.kind_boxes[kind] = QCheckBox(kind_name(kind), self)
            cb.setChecked(kind in selected)
            cb.toggled.connect(self.kinds_changed)
            kl.addWidget(cb)
        self.status = st = QLabel(self)
        st.setWordWrap(True)
        st.linkActivated.connect(self.status_link_activated)
        l.addWidget(st)
        self.scroll_area = sa = QScrollArea(self)
        sa.setWidgetResizable(True)
        self.rows_container = rc = QWidget(sa)
        self.rows_layout = rl = QVBoxLayout(rc)
        rl.addStretch(1)
        sa.setWidget(rc)
        l.addWidget(sa, stretch=1)
        self.service.options_changed.connect(self.regenerate)

    def kinds_changed(self) -> None:
        tprefs['grammar_suggestion_kinds'] = [k for k, cb in self.kind_boxes.items() if cb.isChecked()]
        self.regenerate()

    def regenerate(self) -> None:
        if self.target is not None:
            self.set_target(self.target)

    def cancel(self) -> None:
        for token in self.tokens:
            self.service.cancel_suggestion(token)
        self.tokens = []
        self.pending = 0

    def clear_rows(self) -> None:
        for row in self.rows:
            self.rows_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        self.seen.clear()

    def set_target(self, target: SentenceTarget | None, message: str = '') -> None:
        self.cancel()
        self.clear_rows()
        self.generation += 1
        self.error = ''
        self.missing_model_id, self.missing_variant = '', None
        self.target = target
        if target is None:
            self.sentence_label.setText('')
            self.status.setText(message)
            return
        self.sentence_label.setText(f'<i>{prepare_string_for_xml(target.sentence.text)}</i>')
        self.generate()

    def generate(self) -> None:
        if (t := self.target) is None:
            return
        lang = t.sentence.lang
        model_id = default_model('suggest', lang)
        if model_id is None:
            self.status.setText(_('Suggestions for rewriting sentences are not available for {}').format(prepare_string_for_xml(language_name(lang))))
            return
        if not is_usable(model_id):
            self.missing_model_id, self.missing_variant = model_id, None
            self.show_download_link()
            return
        kinds = [k for k, cb in self.kind_boxes.items() if cb.isChecked()]
        if not kinds:
            self.status.setText(_('Choose the kinds of suggestions to show'))
            return
        self.pending = len(kinds)
        for kind in kinds:
            self.tokens.append(self.service.suggest(self, t.sentence.text, lang, kind, partial(self.on_response, self.generation)))
        self.update_status()

    def show_download_link(self) -> None:
        self.status.setText(
            _('The neural network for suggesting rewrites of sentences has not been downloaded. <a href="{}">Download it</a>.').format('download:')
        )

    def on_response(self, generation: int, r: SuggestResponse) -> None:
        if generation != self.generation or (t := self.target) is None:
            return
        for suggestion in r.suggestions:
            if suggestion.text in self.seen or not can_apply_suggestion(t.paragraph, t.sentence, suggestion.edits):
                continue
            self.seen.add(suggestion.text)
            row = SuggestionRow(t.sentence.text, suggestion, partial(self.apply, suggestion), self.rows_container)
            self.rows_layout.insertWidget(len(self.rows), row)
            self.rows.append(row)
        if r.done:
            self.pending = max(0, self.pending - 1)
            if r.error and not r.cancelled:
                if r.model_id and (variant := as_variant(r.variant)) is not None:
                    self.missing_model_id, self.missing_variant = r.model_id, variant
                    self.cancel()
                else:
                    self.error = r.error
                    print(f'Generating suggestions failed with error: {r.error}\n{r.details}', file=sys.stderr)
        self.update_status()

    def update_status(self) -> None:
        if self.missing_variant is not None:
            self.show_download_link()
        elif self.error:
            self.status.setText(_('Generating suggestions failed with error: {}').format(prepare_string_for_xml(self.error)))
        elif self.pending:
            self.status.setText(_('Generating suggestions, please wait...'))
        elif not self.rows:
            self.status.setText(_('No suggestions, this sentence looks fine'))
        else:
            self.status.setText('')

    def status_link_activated(self, link: str) -> None:
        if (t := self.target) is not None and link == 'download:':
            variants = () if self.missing_variant is None else (self.missing_variant,)
            if ensure_model(self, 'suggest', t.sentence.lang, variants, self.missing_model_id):
                self.regenerate()

    def apply(self, suggestion: Suggestion) -> None:
        if (t := self.target) is not None and self.apply_callback(t, suggestion):
            self.set_target(None)


class RewriteSuggestionsPanel(QWidget):
    """
    A panel showing suggestions for rewriting the sentence the cursor is in.
    The sentence is followed, and suggestions are generated, only while the
    panel is visible.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Returns the editor whose cursor is followed
        self.current_text_edit: Callable[[], TextEdit | None] = lambda: None
        self.timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(SUGGESTION_DELAY), t.timeout.connect(self.update_target)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.suggestions = SuggestionsWidget(self.apply, self)
        l.addWidget(self.suggestions)

    def cursor_moved(self) -> None:
        """Called when the cursor moves or the current editor changes"""
        if self.isVisible():
            self.timer.start()

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        self.timer.start()

    def hideEvent(self, a0: QHideEvent | None) -> None:
        super().hideEvent(a0)
        self.timer.stop()
        self.suggestions.set_target(None)

    def update_target(self) -> None:
        if not self.isVisible():
            return
        te = self.current_text_edit()
        target = None
        if te is not None and not sip.isdeleted(te) and te.grammar_checker is not None:
            target = te.grammar_checker.sentence_target(te.textCursor().position())
        if target is None:
            self.suggestions.set_target(None, _('Place the cursor in a sentence in an HTML file to see suggestions for rewriting it.'))
        elif (current := self.suggestions.target) is None or current.sentence != target.sentence:
            self.suggestions.set_target(target)

    def apply(self, target: SentenceTarget, suggestion: Suggestion) -> bool:
        te = self.current_text_edit()
        if te is None or sip.isdeleted(te) or te.grammar_checker is None:
            return False
        if ok := te.grammar_checker.apply_suggestion(target, suggestion):
            # Show suggestions for the rewritten sentence
            self.timer.start()
        return ok


class RewritePopup(Dialog):
    """A window showing suggestions for rewriting a sentence"""

    def __init__(self, target: SentenceTarget, apply: Callable[[SentenceTarget, Suggestion], bool], parent: QWidget | None = None) -> None:
        self.target, self.apply_callback = target, apply
        Dialog.__init__(self, _('Suggestions for rewriting the sentence'), 'grammar-rewrite-popup', parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.suggestions = SuggestionsWidget(self.apply, self)
        l.addWidget(self.suggestions)
        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Close)
        l.addWidget(self.bb)
        self.suggestions.set_target(self.target)

    def apply(self, target: SentenceTarget, suggestion: Suggestion) -> bool:
        ok = self.apply_callback(target, suggestion)
        if ok:
            self.accept()
        return ok

    def accept(self) -> None:
        self.suggestions.cancel()
        Dialog.accept(self)

    def reject(self) -> None:
        self.suggestions.cancel()
        Dialog.reject(self)

    def sizeHint(self) -> QSize:
        return QSize(650, 350)


def show_rewrite_popup(parent: QWidget, target: SentenceTarget, apply: Callable[[SentenceTarget, Suggestion], bool], pos: QPoint | None = None) -> RewritePopup:
    d = RewritePopup(target, apply, parent)
    if pos is not None:
        d.move(pos)
    d.show()
    return d


# }}}


# Check grammar tool {{{


def checkable_names(container: Container) -> list[str]:
    return [name for name, linear in container.spine_names if container.mime_map.get(name) in OEB_DOCS]


class BookIssue(NamedTuple):
    file_name: str
    # The language used for text without a specified language when the file was checked
    default_lang: str
    ref: ParagraphRef
    result: ParagraphResult
    issue: Issue
    key: IgnoreKey
    # The position of the issue in the book, for sorting
    file_index: int
    paragraph_index: int

    @property
    def text(self) -> str:
        return self.result.text[self.issue.start : self.issue.end]

    @property
    def sort_key(self) -> tuple[int, int, int, int]:
        return self.file_index, self.paragraph_index, self.issue.start, self.issue.end

    def context(self, width: int = 30) -> tuple[str, str, str]:
        t = self.result.text
        s, e = self.issue.start, self.issue.end
        before = t[max(0, s - width) : s]
        after = t[e : e + width]
        return ('…' if s > width else '') + before, t[s:e], after + ('…' if e + width < len(t) else '')


class IssuesModel(QAbstractTableModel):
    COLUMNS = (_('File'), _('Text'), _('Issue'), _('Type'))

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.all_issues: list[BookIssue] = []
        self.items: list[BookIssue] = []
        self.filter_text = ''
        self.issue_type = ''
        self.service = grammar_service()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or not 0 <= index.row() < len(self.items):
            return None
        x = self.items[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return x.file_name
            if col == 1:
                before, text, after = x.context(15)
                return f'{before}[{text}]{after}'.replace('\n', ' ')
            if col == 2:
                return rule_description(x.issue)
            if col == 3:
                return x.issue.issue_type
        elif role == Qt.ItemDataRole.ToolTipRole and col in (1, 2):
            return issue_html(x.issue)
        return None

    def is_visible(self, x: BookIssue) -> bool:
        if not is_shown(x.issue, x.key, self.service):
            return False
        if self.issue_type and x.issue.issue_type != self.issue_type:
            return False
        if self.filter_text:
            q = self.filter_text
            return any(primary_contains(q, t) for t in (x.text, x.issue.message, x.issue.short_message, x.file_name))
        return True

    def rebuild(self) -> None:
        self.beginResetModel()
        self.items = [x for x in self.all_issues if self.is_visible(x)]
        self.endResetModel()

    def set_issues(self, issues: list[BookIssue]) -> None:
        self.all_issues = sorted(issues, key=lambda x: x.sort_key)
        self.rebuild()

    def issue_types(self) -> list[str]:
        return sorted({x.issue.issue_type for x in self.all_issues}, key=primary_sort_key)

    def row_for(self, x: BookIssue | None) -> int:
        if x is None:
            return -1
        for i, y in enumerate(self.items):
            if y.key == x.key and y.file_name == x.file_name and y.ref == x.ref:
                return i
        return -1

    def issue_for_row(self, row: int) -> BookIssue | None:
        return self.items[row] if 0 <= row < len(self.items) else None


class PendingFile(NamedTuple):
    # Identifies the check of the file, results from earlier checks of it are ignored
    check_id: int
    file_index: int
    default_lang: str
    paragraphs: list[Paragraph]
    refs: list[ParagraphRef]


class GrammarCheck(Dialog):
    # Emitted before reading files from the container, so that changes in
    # editors are committed to it
    commit_requested = pyqtSignal()
    # Emitted with the names of the files changed by corrections
    files_changed = pyqtSignal(object)
    # Emitted with a BookIssue to show it in the editor
    show_issue = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        self.service = grammar_service()
        self.files: dict[str, PendingFile] = {}
        self.issues: dict[str, list[BookIssue]] = {}
        self.tokens: list[int] = []
        self.check_ids = count(1)
        self.paragraphs_total = self.paragraphs_done = 0
        self.errors: list[tuple[str, str]] = []
        self.missing_languages: set[str] = set()
        self.unsupported_languages: set[str] = set()
        # Maps the ids of models the worker reported as not downloaded to the missing variants
        self.missing_models: dict[str, set[Variant]] = {}
        # Maps the names of the files changed by the last change to their data before and after it
        self.undo_data: dict[str, tuple[bytes, bytes]] = {}
        Dialog.__init__(self, _('Check grammar'), 'grammar-check', parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.update_timer = t = QTimer(self)
        t.setSingleShot(True), t.setInterval(300), t.timeout.connect(self.update_model)
        self.service.options_changed.connect(self.refresh)
        self.service.ignored_changed.connect(self.ignored_changed)

    def setup_ui(self) -> None:
        self.setWindowIcon(QIcon.ic('grammar-check.png'))
        self.l = l = QVBoxLayout(self)

        self.banner = b = QLabel(self)
        b.setWordWrap(True), b.setVisible(False)
        b.linkActivated.connect(self.banner_link_activated)
        l.addWidget(b)

        self.filter_text = t = QLineEdit(self)
        t.setPlaceholderText(_('Filter the list of issues'))
        t.setClearButtonEnabled(True)
        t.textChanged.connect(self.do_filter)
        self.type_filter = tf = QComboBox(self)
        tf.addItem(_('All types of issues'), '')
        tf.currentIndexChanged.connect(self.do_filter)
        h = QHBoxLayout()
        h.addWidget(t, stretch=1), h.addWidget(tf)
        l.addLayout(h)

        self.splitter = s = QSplitter(self)
        l.addWidget(s, stretch=1)
        self.issues_view = v = QTableView(self)
        v.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        v.setWordWrap(False)
        v.setAlternatingRowColors(True)
        vh = v.verticalHeader()
        assert vh is not None
        vh.setVisible(False)
        hh = v.horizontalHeader()
        assert hh is not None
        hh.setStretchLastSection(True)
        self.model = m = IssuesModel(self)
        v.setModel(m)
        sm = v.selectionModel()
        assert sm is not None
        sm.currentRowChanged.connect(self.current_issue_changed)
        v.doubleClicked.connect(self.show_current_issue)
        state = tprefs.get('grammar-check-table-state')
        if state is None:
            for col, width in enumerate((120, 250, 200)):
                v.setColumnWidth(col, width)
        else:
            hh.restoreState(state)
        s.addWidget(v)

        self.details = d = QWidget(self)
        dl = QVBoxLayout(d)
        dl.setContentsMargins(0, 0, 0, 0)
        self.description = desc = QTextBrowser(self)
        desc.setOpenLinks(False)
        desc.anchorClicked.connect(self.description_link_clicked)
        dl.addWidget(desc, stretch=2)
        la = QLabel(_('&Replace with:'), self)
        dl.addWidget(la)
        self.replacements = rl = QListWidget(self)
        la.setBuddy(rl)
        rl.currentItemChanged.connect(self.current_replacement_changed)
        rl.itemActivated.connect(self.change_current)
        dl.addWidget(rl, stretch=1)
        self.replacement = rep = QLineEdit(self)
        rep.setPlaceholderText(_('The replacement text'))
        rep.returnPressed.connect(self.change_current)
        dl.addWidget(rep)
        bl = FlowLayout()
        dl.addLayout(bl)

        def button(text: str, icon: str, tooltip: str, slot: Callable[[], None]) -> QPushButton:
            b = QPushButton(QIcon.ic(icon), text, self)
            b.setAutoDefault(False)
            b.setToolTip('<p>' + tooltip)
            b.clicked.connect(slot)
            bl.addWidget(b)
            return b

        self.change_button = button(_('&Change'), 'ok.png', _('Replace the text of the issue with the replacement'), self.change_current)
        self.show_button = button(_('&Show in editor'), 'edit_input.png', _('Show this issue in the editor'), self.show_current_issue)
        self.ignore_button = button(_('&Ignore'), 'edit-clear.png', _('Ignore this issue for the rest of this session'), self.ignore_current)
        self.suggest_button = button(
            _('Suggest &rewrites'),
            'grammar-check.png',
            _('Show suggestions for rewriting the sentence containing this issue, generated by a neural network'),
            self.suggest_rewrites,
        )
        self.disable_rule_button = button(
            _('&Disable rule'),
            'list_remove.png',
            _('Stop checking for this kind of issue. Disabled rules can be enabled again with the Manage disabled rules button.'),
            self.disable_current_rule,
        )
        s.addWidget(d)
        s.setStretchFactor(0, 3), s.setStretchFactor(1, 2)

        self.progress_bar = pb = QProgressBar(self)
        pb.setVisible(False)
        l.addWidget(pb)

        h = QHBoxLayout()
        l.addLayout(h)
        ab = FlowLayout()
        h.addLayout(ab, stretch=1)

        def action_button(text: str, icon: str, tooltip: str, slot: Callable[[], None]) -> QPushButton:
            b = QPushButton(QIcon.ic(icon), text, self)
            b.setAutoDefault(False)
            b.setToolTip('<p>' + tooltip)
            b.clicked.connect(slot)
            ab.addWidget(b)
            return b

        action_button(_('&Refresh'), 'view-refresh.png', _('Check the book again, useful if you have edited it since opening this tool'), self.refresh)
        action_button(_('&Undo last change'), 'edit-undo.png', _('Undo the last correction made with this tool'), self.undo_last_change)
        action_button(_('&Manage disabled rules'), 'config.png', _('Enable rules that were disabled'), self.manage_disabled_rules)
        self.picky = p = QCheckBox(_('&Picky'), self)
        p.setToolTip('<p>' + _('Also check for stylistic issues that are not errors, such as wordiness and overused phrases'))
        p.setChecked(bool(tprefs['grammar_picky']))
        p.toggled.connect(self.picky_toggled)
        ab.addWidget(p)
        self.deep = dc = QCheckBox(_('D&eep check'), self)
        dc.setToolTip(
            '<p>'
            + _(
                'Also check every sentence with a neural network, which finds errors the rules miss, but is slower and can'
                ' find errors that are not errors. Needs the neural network to be downloaded and is only available for English.'
            )
        )
        dc.setChecked(bool(tprefs['grammar_deep_check']))
        dc.toggled.connect(self.deep_toggled)
        ab.addWidget(dc)
        h.addWidget(self.bb, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Close)
        self.update_details()

    def sizeHint(self) -> QSize:
        return QSize(1100, 700)

    # Checking {{{
    def show(self) -> None:
        Dialog.show(self)
        self.undo_data.clear()
        QTimer.singleShot(0, self.refresh)

    def cancel(self) -> None:
        for token in self.tokens:
            self.service.cancel(token)
        self.tokens = []

    def book_changed(self) -> None:
        self.cancel()
        self.files.clear()
        self.issues.clear()
        self.undo_data.clear()
        self.model.set_issues([])
        self.paragraphs_total = self.paragraphs_done = 0
        self.update_progress()
        if self.isVisible():
            QTimer.singleShot(0, self.refresh)

    def refresh(self, *a: object) -> None:
        if not self.isVisible() or current_container() is None:
            return
        self.commit_requested.emit()
        self.cancel()
        self.files.clear()
        self.issues.clear()
        self.errors.clear()
        self.missing_languages.clear()
        self.unsupported_languages.clear()
        self.missing_models.clear()
        self.paragraphs_total = self.paragraphs_done = 0
        # The current list of issues is kept until the new results arrive,
        # so that the current issue, or its row, is preserved
        self.check_files(checkable_names(current_container()), update_now=False)

    def check_files(self, names: Sequence[str], update_now: bool = True) -> None:
        container = current_container()
        all_names = checkable_names(container)
        default_lang = book_language()
        by_lang: dict[str, list[tuple[str, int, int]]] = {}
        sent = False
        with BusyCursor():
            for name in names:
                if name not in all_names:
                    continue
                try:
                    source = container.raw_data(name)
                except (OSError, ValueError) as e:
                    self.errors.append((_('Failed to read {0} with error: {1}').format(name, e), traceback.format_exc()))
                    continue
                if not isinstance(source, str):
                    continue
                paragraphs = extract_paragraphs(source, default_lang)
                pf = self.files[name] = PendingFile(next(self.check_ids), all_names.index(name), default_lang, paragraphs, paragraph_refs(paragraphs))
                self.issues[name] = []
                for lang, indices in paragraphs_by_language(paragraphs, default_lang).items():
                    by_lang.setdefault(lang, []).extend((name, i, pf.check_id) for i in indices)
        for lang, items in by_lang.items():
            status = self.service.language_status(lang)
            if status == 'missing':
                self.missing_languages.add(lang)
                continue
            if status == 'unsupported':
                self.unsupported_languages.add(lang)
                continue
            texts = [self.files[name].paragraphs[i].text for name, i, check_id in items]
            self.paragraphs_total += len(texts)
            sent = True
            self.tokens.append(self.service.check(self, texts, lang, partial(self.on_response, tuple(items))))
        self.update_progress()
        self.update_banner()
        if update_now or not sent:
            self.update_model()
        self.report_errors()

    def on_response(self, items: tuple[tuple[str, int, int], ...], r: CheckResponse) -> None:
        for i, result in r.results.items():
            name, pidx, check_id = items[i]
            if (pf := self.files.get(name)) is None or pf.check_id != check_id:
                continue
            p = pf.paragraphs[pidx]
            for issue in visible_issues(p, result.issues):
                self.issues[name].append(BookIssue(name, pf.default_lang, pf.refs[pidx], result, issue, ignore_key(result, issue), pf.file_index, pidx))
        self.paragraphs_done += len(r.results)
        if r.model_id and (variant := as_variant(r.variant)) is not None:
            # Either the deep check continues with only the rules, or, for a
            # failed request, the model is offered for download instead of
            # reporting an error
            self.missing_models.setdefault(r.model_id, set()).add(variant)
            self.update_banner()
        if r.done:
            self.paragraphs_done = min(self.paragraphs_done, self.paragraphs_total)
            if r.error and not r.cancelled:
                if r.language_data:
                    self.missing_languages.add(r.language_data)
                    self.update_banner()
                elif not r.model_id:
                    self.errors.append((r.error, r.details))
                    self.report_errors()
        self.update_progress()
        if not self.update_timer.isActive():
            self.update_timer.start()

    def update_progress(self) -> None:
        pb = self.progress_bar
        if self.paragraphs_done >= self.paragraphs_total:
            pb.setVisible(False)
            self.update_title()
            return
        pb.setVisible(True)
        pb.setMaximum(self.paragraphs_total)
        pb.setValue(self.paragraphs_done)
        pb.setFormat(_('Checked %v of %m paragraphs'))
        self.update_title()

    def update_title(self) -> None:
        n = self.model.rowCount()
        if self.paragraphs_done < self.paragraphs_total:
            self.setWindowTitle(_('Check grammar: checking, {} issues found so far').format(n))
        else:
            self.setWindowTitle(_('Check grammar: {} issues found').format(n))

    def report_errors(self) -> None:
        if self.errors:
            errors, self.errors = self.errors, []
            error_dialog(
                self,
                _('Grammar check failed'),
                _('Checking the grammar failed with error: {}').format(errors[0][0]),
                det_msg='\n\n'.join(f'{e}\n{d}' for e, d in errors),
                show=True,
            )

    def update_banner(self) -> None:
        parts = []
        for lang in sorted(self.missing_languages):
            parts.append(
                _('The data needed for checking {0} has not been downloaded. <a href="{1}">Download it</a>.').format(
                    prepare_string_for_xml(language_name(lang)), f'download-data:{lang}'
                )
            )
        if self.missing_models:
            parts.append(_('The neural network for deep checks has not been downloaded. <a href="download-model:">Download it</a>.'))
        if self.unsupported_languages:
            names = ', '.join(sorted(language_name(x) for x in self.unsupported_languages))
            parts.append(_('Text in these languages is not checked as they are not supported: {}').format(prepare_string_for_xml(names)))
        self.banner.setText('<br>'.join(parts))
        self.banner.setVisible(bool(parts))

    def banner_link_activated(self, link: str) -> None:
        kind, _sep, lang = link.partition(':')
        if kind == 'download-data':
            if ensure_language_data(self, lang):
                self.refresh()
        elif kind == 'download-model':
            missing = dict(self.missing_models)
            if all(ensure_model(self, 'check', book_language(), tuple(variants), model_id) for model_id, variants in missing.items()):
                self.service.options_changed.emit()

    # }}}

    # Display {{{
    def update_model(self) -> None:
        current, row = self.current_issue, max(0, self.issues_view.currentIndex().row())
        self.model.set_issues([x for issues in self.issues.values() for x in issues])
        tf = self.type_filter
        selected = tf.currentData()
        types = self.model.issue_types()
        if types != [tf.itemData(i) for i in range(1, tf.count())]:
            tf.blockSignals(True)
            while tf.count() > 1:
                tf.removeItem(1)
            for t in types:
                tf.addItem(t.capitalize(), t)
            idx = tf.findData(selected)
            tf.setCurrentIndex(max(0, idx))
            tf.blockSignals(False)
            if idx < 0 and selected:
                self.do_filter()
                return
        self.restore_current(current, row)
        self.update_title()

    def restore_current(self, current: BookIssue | None, fallback_row: int = 0) -> None:
        row = self.model.row_for(current)
        if row < 0:
            row = min(fallback_row, self.model.rowCount() - 1)
        if row > -1:
            idx = self.model.index(row, 0)
            self.issues_view.setCurrentIndex(idx)
            self.issues_view.scrollTo(idx)
        else:
            self.update_details()

    def do_filter(self, *a: object) -> None:
        current = self.current_issue
        self.model.filter_text = self.filter_text.text().strip()
        self.model.issue_type = str(self.type_filter.currentData() or '')
        self.model.rebuild()
        self.restore_current(current)
        self.update_title()

    def ignored_changed(self) -> None:
        current, row = self.current_issue, self.issues_view.currentIndex().row()
        self.model.rebuild()
        self.restore_current(current, max(0, row))
        self.update_title()

    @property
    def current_issue(self) -> BookIssue | None:
        return self.model.issue_for_row(self.issues_view.currentIndex().row())

    def current_issue_changed(self, *a: object) -> None:
        self.update_details()

    def update_details(self) -> None:
        x = self.current_issue
        self.replacements.clear()
        self.replacement.clear()
        for button in (self.change_button, self.show_button, self.ignore_button, self.suggest_button, self.disable_rule_button):
            button.setEnabled(x is not None)
        if x is None:
            self.description.setHtml('<p>' + _('No issue selected'))
            return
        issue = x.issue
        s, e = containing_sentence(x.result.sentences, issue.start, issue.end) or (0, len(x.result.text))
        sentence = x.result.text[s:e]
        a, b = issue.start - s, issue.end - s
        marked = (
            prepare_string_for_xml(sentence[:a])
            + '<b style="text-decoration: underline">'
            + (prepare_string_for_xml(sentence[a:b]) or '&nbsp;')
            + '</b>'
            + prepare_string_for_xml(sentence[b:])
        )
        html = f'<h3>{prepare_string_for_xml(issue.short_message)}</h3>' if issue.short_message else ''
        html += f'<p>{prepare_string_for_xml(issue.message)}</p><p style="font-style: italic">{marked}</p>'
        html += '<p style="font-size: small">' + prepare_string_for_xml(_('In: {}').format(x.file_name))
        if issue.url:
            html += f' &mdash; <a href="{prepare_string_for_xml(issue.url, True)}">{_("Explain")}</a>'
        html += '</p>'
        self.description.setHtml(html)
        for r in issue.replacements:
            QListWidgetItem(r or _('(remove the text)'), self.replacements).setData(Qt.ItemDataRole.UserRole, r)
        if issue.replacements:
            self.replacements.setCurrentRow(0)

    def current_replacement_changed(self, item: QListWidgetItem | None, *a: object) -> None:
        if item is not None:
            self.replacement.setText(str(item.data(Qt.ItemDataRole.UserRole)))

    def description_link_clicked(self, url: QUrl) -> None:
        open_url(url)

    # }}}

    # Actions {{{
    def show_current_issue(self, *a: object) -> None:
        if (x := self.current_issue) is not None:
            self.show_issue.emit(x)

    def change_current(self, *a: object) -> None:
        x = self.current_issue
        if x is None:
            return
        replacement = self.replacement.text()
        if not replacement and '' not in x.issue.replacements:
            error_dialog(self, _('No replacement'), _('You must specify the text to replace the text of the issue with'), show=True)
            return
        self.modify_file(x, lambda source: correct_source(source, x.default_lang, x.ref, x.issue, replacement))

    def modify_file(self, x: BookIssue, transform: Callable[[str], str]) -> bool:
        """Change the file containing the issue with transform, then check it again. Returns True if the file was changed."""
        self.commit_requested.emit()
        container = current_container()
        name = x.file_name
        try:
            raw = container.raw_data(name, decode=False)
            source = container.raw_data(name)
            if not isinstance(source, str):
                raise TypeError(f'{name} is not a text file')
            changed = replace_encoding_declarations(transform(source), enc='utf-8', limit=4 * 1024)[0]
            new_raw = changed.encode('utf-8')
            with container.open(name, 'wb') as f:
                f.write(new_raw)
        except EditNotPossible as e:
            error_dialog(
                self,
                _('Cannot change'),
                _(
                    'Cannot make this change, as the text has changed since it was checked or contains text that must not be changed.'
                    ' Click Refresh to check the book again.'
                ),
                det_msg=str(e),
                show=True,
            )
            return False
        except (OSError, ValueError, TypeError) as e:
            error_dialog(self, _('Cannot change'), _('Failed to change {0} with error: {1}').format(name, e), det_msg=traceback.format_exc(), show=True)
            return False
        self.undo_data = {name: (raw, new_raw)}
        row = self.issues_view.currentIndex().row()
        self.files_changed.emit({name})
        # Show the next issue while the file is checked again
        self.issues[name] = [y for y in self.issues.get(name, ()) if y is not x]
        self.model.set_issues([y for issues in self.issues.values() for y in issues])
        self.restore_current(None, row)
        self.check_files((name,), update_now=False)
        return True

    def suggest_rewrites(self) -> None:
        x = self.current_issue
        if x is None:
            return
        pf = self.files.get(x.file_name)
        if pf is None or x.paragraph_index >= len(pf.refs) or pf.refs[x.paragraph_index] != x.ref:
            error_dialog(self, _('Text changed'), _('The text has changed since it was checked, click Refresh to check the book again.'), show=True)
            return

        def apply(target: SentenceTarget, suggestion: Suggestion) -> bool:
            return self.modify_file(x, lambda source: apply_suggestion(source, target.default_lang, target.sentence, suggestion.edits))

        show_rewrite_popup(self, sentence_for_issue(pf, x), apply)

    def undo_last_change(self) -> None:
        if not self.undo_data:
            error_dialog(self, _('No change'), _('There is no correction to undo'), show=True)
            return
        # Changes made in the editors since the last change must not be lost
        self.commit_requested.emit()
        container = current_container()
        try:
            for name, (before, after) in self.undo_data.items():
                if container.raw_data(name, decode=False) != after:
                    error_dialog(
                        self,
                        _('Cannot undo'),
                        _('{} has been edited since the change was made, use undo in the editor instead.').format(name),
                        show=True,
                    )
                    return
            for name, (before, after) in self.undo_data.items():
                with container.open(name, 'wb') as f:
                    f.write(before)
        except OSError as e:
            error_dialog(self, _('Cannot undo'), _('Failed to undo the change with error: {}').format(e), det_msg=traceback.format_exc(), show=True)
            return
        names, self.undo_data = tuple(self.undo_data), {}
        self.files_changed.emit(set(names))
        self.check_files(names)

    def ignore_current(self) -> None:
        if (x := self.current_issue) is not None:
            self.service.ignore(x.key)

    def disable_current_rule(self) -> None:
        if (x := self.current_issue) is not None:
            self.service.disable_rule(x.issue.rule_id, rule_description(x.issue))

    def manage_disabled_rules(self) -> None:
        d = ManageDisabledRules(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.service.set_disabled_rules(d.rules)

    def picky_toggled(self, checked: bool) -> None:
        tprefs['grammar_picky'] = checked
        self.service.options_changed.emit()

    def deep_toggled(self, checked: bool) -> None:
        # Offer to download the model for the language of the book, if there is
        # one. Models needed for text in other languages are reported by the
        # check and can be downloaded from the banner.
        lang = book_language()
        if checked and default_model('check', lang) and not ensure_model(self, 'check', lang):
            self.deep.blockSignals(True)
            self.deep.setChecked(False)
            self.deep.blockSignals(False)
            return
        tprefs['grammar_deep_check'] = checked
        self.service.options_changed.emit()

    # }}}

    def save_table_state(self) -> None:
        hh = self.issues_view.horizontalHeader()
        assert hh is not None
        tprefs['grammar-check-table-state'] = bytearray(hh.saveState())
        self.cancel()

    def accept(self) -> None:
        self.save_table_state()
        Dialog.accept(self)

    def reject(self) -> None:
        self.save_table_state()
        Dialog.reject(self)


class ManageDisabledRules(Dialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        self.rules = dict(disabled_rules())
        Dialog.__init__(self, _('Manage disabled grammar rules'), 'grammar-disabled-rules', parent)

    def setup_ui(self) -> None:
        self.l = l = QVBoxLayout(self)
        la = QLabel(_('These rules are not used when checking grammar. Select rules and click Enable to use them again.'), self)
        la.setWordWrap(True)
        l.addWidget(la)
        self.rules_list = rl = QListWidget(self)
        rl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for rule_id, description in sorted(self.rules.items(), key=lambda x: primary_sort_key(x[1] or x[0])):
            text = f'{description} ({rule_id})' if description else rule_id
            QListWidgetItem(text, rl).setData(Qt.ItemDataRole.UserRole, rule_id)
        l.addWidget(rl)
        b = QPushButton(QIcon.ic('plus.png'), _('&Enable selected rules'), self)
        b.clicked.connect(self.enable_selected)
        b.setAutoDefault(False)
        h = QHBoxLayout()
        h.addWidget(b), h.addStretch(1), h.addWidget(self.bb)
        l.addLayout(h)

    def enable_selected(self) -> None:
        for item in self.rules_list.selectedItems():
            self.rules.pop(str(item.data(Qt.ItemDataRole.UserRole)), None)
            self.rules_list.takeItem(self.rules_list.row(item))

    def sizeHint(self) -> QSize:
        return QSize(500, 400)


# }}}


def develop() -> None:
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book import set_book_locale, set_current_container

    app = Application([])
    set_current_container(get_container(sys.argv[-1], tweak_mode=True))
    set_book_locale(current_container().mi.language)
    d = GrammarCheck()
    d.show()
    d.exec()
    shutdown_grammar_service()
    del app
