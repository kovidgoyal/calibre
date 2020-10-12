#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import json
import numbers
import sys
from collections import namedtuple
from itertools import repeat

try:
    from PyQt5 import sip
except ImportError:
    import sip
from PyQt5.Qt import QApplication, QEventLoop, pyqtSignal
from PyQt5.QtWebEngineWidgets import (
    QWebEnginePage, QWebEngineProfile, QWebEngineScript
)

from calibre import detect_ncpus as cpu_count, prints
from calibre.ebooks.oeb.polish.check.base import ERROR, WARN, BaseError
from calibre.gui2 import must_use_qt
from calibre.gui2.webengine import secure_webengine


class CSSParseError(BaseError):
    level = ERROR
    is_parsing_error = True


class CSSError(BaseError):
    level = ERROR


class CSSWarning(BaseError):
    level = WARN


def as_int_or_none(x):
    if x is not None and not isinstance(x, numbers.Integral):
        try:
            x = int(x)
        except Exception:
            x = None
    return x


def message_to_error(message, name, line_offset=0):
    rule = message.get('rule', {})
    rule_id = rule.get('id') or ''
    cls = CSSWarning
    if message.get('type') == 'error':
        cls = CSSParseError if rule.get('name') == 'Parsing Errors' else CSSError
    title = message.get('message') or _('Unknown error')
    line = as_int_or_none(message.get('line'))
    col = as_int_or_none(message.get('col'))
    if col is not None:
        col -= 1
    if line is not None:
        line += line_offset
    ans = cls(title, name, line, col)
    ans.HELP = rule.get('desc') or ''
    ans.css_rule_id = rule_id
    if ans.HELP and 'url' in rule:
        ans.HELP += ' ' + _('See <a href="{}">detailed description</a>.').format(rule['url'])
    return ans


def csslint_js():
    ans = getattr(csslint_js, 'ans', None)
    if ans is None:
        ans = csslint_js.ans = P('csslint.js', data=True, allow_user_override=False).decode('utf-8') + '''

        window.check_css =  function(src) {
            var rules = CSSLint.getRules();
            var ruleset = {};
            var ignored_rules = {
                'order-alphabetical': 1,
                'font-sizes': 1,
                'zero-units': 1,
                'bulletproof-font-face': 1,
                'import': 1,
                'box-model': 1,
                'adjoining-classes': 1,
                'box-sizing': 1,
                'compatible-vendor-prefixes': 1,
                'text-indent': 1,
                'unique-headings': 1,
                'fallback-colors': 1,
                'font-faces': 1,
                'regex-selectors': 1,
                'universal-selector': 1,
                'unqualified-attributes': 1,
                'overqualified-elements': 1,
                'shorthand': 1,
                'duplicate-background-images': 1,
                'floats': 1,
                'ids': 1,
                'gradients': 1
            };
            var error_rules = {
                'known-properties': 1,
                'duplicate-properties': 1,
                'vendor-prefix': 1
            };

            for (var i = 0; i < rules.length; i++) {
                var rule = rules[i];
                if (!ignored_rules[rule.id] && rule.browsers === "All") ruleset[rule.id] = error_rules[rule.id] ? 2 : 1;
            }
            var result = CSSLint.verify(src, ruleset);
            return result;
        }
        document.title = 'ready';
        '''
    return ans


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = create_profile.ans = QWebEngineProfile(QApplication.instance())
        s = QWebEngineScript()
        s.setName('csslint.js')
        s.setSourceCode(csslint_js())
        s.setWorldId(QWebEngineScript.ApplicationWorld)
        ans.scripts().insert(s)
    return ans


class Worker(QWebEnginePage):

    work_done = pyqtSignal(object, object)

    def __init__(self):
        must_use_qt()
        QWebEnginePage.__init__(self, create_profile(), QApplication.instance())
        self.titleChanged.connect(self.title_changed)
        secure_webengine(self.settings())
        self.console_messages = []
        self.ready = False
        self.working = False
        self.pending = None
        self.setHtml('')

    def title_changed(self, new_title):
        if new_title == 'ready':
            self.ready = True
            if self.pending is not None:
                self.check_css(self.pending)
                self.pending = None

    def javaScriptConsoleMessage(self, level, msg, lineno, source_id):
        msg = '{}:{}:{}'.format(source_id, lineno, msg)
        self.console_messages.append(msg)
        try:
            print(msg)
        except Exception:
            pass

    def check_css(self, src):
        self.working = True
        self.console_messages = []
        self.runJavaScript(
            'window.check_css({})'.format(json.dumps(src)), QWebEngineScript.ApplicationWorld, self.check_done)

    def check_css_when_ready(self, src):
        if self.ready:
            self.check_css(src)
        else:
            self.working = True
            self.pending = src

    def check_done(self, result):
        self.working = False
        self.work_done.emit(self, result)


class Pool(object):

    def __init__(self):
        self.workers = []
        self.max_workers = cpu_count()

    def add_worker(self):
        w = Worker()
        w.work_done.connect(self.work_done)
        self.workers.append(w)

    def check_css(self, css_sources):
        self.pending = list(enumerate(css_sources))
        self.results = list(repeat(None, len(css_sources)))
        self.working = True
        self.assign_work()
        app = QApplication.instance()
        while self.working:
            app.processEvents(QEventLoop.WaitForMoreEvents | QEventLoop.ExcludeUserInputEvents)
        return self.results

    def assign_work(self):
        while self.pending:
            if len(self.workers) < self.max_workers:
                self.add_worker()
            for w in self.workers:
                if not w.working:
                    idx, src = self.pending.pop()
                    w.result_idx = idx
                    w.check_css_when_ready(src)
                    break
            else:
                break

    def work_done(self, worker, result):
        if not isinstance(result, dict):
            result = worker.console_messages
        self.results[worker.result_idx] = result
        self.assign_work()
        if not self.pending and not [w for w in self.workers if w.working]:
            self.working = False

    def shutdown(self):

        def safe_delete(x):
            if not sip.isdeleted(x):
                sip.delete(x)

        tuple(map(safe_delete, self.workers))
        self.workers = []


pool = Pool()
shutdown = pool.shutdown
atexit.register(shutdown)
Job = namedtuple('Job', 'name css line_offset')


def create_job(name, css, line_offset=0, is_declaration=False):
    if is_declaration:
        css = 'div{\n' + css + '\n}'
        line_offset -= 1
    return Job(name, css, line_offset)


def check_css(jobs):
    errors = []
    if not jobs:
        return errors
    results = pool.check_css([j.css for j in jobs])
    for job, result in zip(jobs, results):
        if isinstance(result, dict):
            for msg in result['messages']:
                err = message_to_error(msg, job.name, job.line_offset)
                if err is not None:
                    errors.append(err)
        elif isinstance(result, list) and result:
            errors.append(CSSParseError(_('Failed to process CSS in {name} with errors: {errors}').format(
                name=job.name, errors='\n'.join(result)), job.name))
        else:
            errors.append(CSSParseError(_('Failed to process CSS in {name}').format(name=job.name), job.name))
    return errors


def main():
    with open(sys.argv[-1], 'rb') as f:
        css = f.read().decode('utf-8')
    errors = check_css([create_job(sys.argv[-1], css)])
    for error in errors:
        prints(error)


if __name__ == '__main__':
    try:
        main()
    finally:
        shutdown()
