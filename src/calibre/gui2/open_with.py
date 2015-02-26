#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re, shlex, cPickle
from collections import defaultdict
from threading import Thread
from functools import partial

from PyQt5.Qt import (
    QApplication, QStackedLayout, QVBoxLayout, QWidget, QLabel, Qt,
    QListWidget, QSize, pyqtSignal, QListWidgetItem, QIcon, QByteArray,
    QBuffer, QPixmap)

from calibre import force_unicode, walk, guess_type, prints, as_unicode
from calibre.constants import iswindows, isosx, filesystem_encoding, cache_dir
from calibre.gui2 import error_dialog, choose_files
from calibre.gui2.widgets2 import Dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.config import JSONConfig
from calibre.utils.icu import numeric_sort_key as sort_key
from calibre.utils.localization import canonicalize_lang, get_lang

DESC_ROLE = Qt.UserRole
ENTRY_ROLE = DESC_ROLE + 1

def pixmap_to_data(pixmap):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, 'PNG')
    return bytearray(ba.data())

def run_program(entry, path, parent):
    import subprocess
    cmdline = entry_to_cmdline(entry, path)
    print('Running Open With commandline:', repr(cmdline))
    try:
        process = subprocess.Popen(cmdline)
    except Exception as err:
        return error_dialog(
            parent, _('Failed to run'), _(
            'Failed to run program, click "Show Details" for more information'),
            det_msg='Command line: %r\n%s' %(cmdline, as_unicode(err)))
    t = Thread(name='WaitProgram', target=process.wait)
    t.daemon = True
    t.start()

if iswindows:
    oprefs = JSONConfig('windows_open_with')
    run_program
    def run_program(entry, path, parent):
        raise NotImplementedError()

elif isosx:
    oprefs = JSONConfig('osx_open_with')
else:
    oprefs = JSONConfig('xdg_open_with')
    # XDG find_programs {{{
    def parse_localized_key(key):
        name, rest = key.partition('[')[0::2]
        if not rest:
            return name, None
        rest = rest[:-1]
        lang = re.split(r'[_.@]', rest)[0]
        return name, canonicalize_lang(lang)

    def unquote_exec(val):
        val = val.replace(r'\\', '\\')
        return shlex.split(val)

    def parse_desktop_file(path):
        gpat = re.compile(r'^\[(.+?)\]\s*$')
        kpat = re.compile(r'^([-a-zA-Z0-9\[\]@_.]+)\s*=\s*(.+)$')
        try:
            with open(path, 'rb') as f:
                raw = f.read().decode('utf-8')
        except (EnvironmentError, UnicodeDecodeError):
            return
        group = None
        ans = {}
        ans['desktop_file_path'] = path
        for line in raw.splitlines():
            m = gpat.match(line)
            if m is not None:
                if group == 'Desktop Entry':
                    break
                group = m.group(1)
                continue
            if group == 'Desktop Entry':
                m = kpat.match(line)
                if m is not None:
                    k, v = m.group(1), m.group(2)
                    if k == 'Hidden' and v == 'true':
                        return
                    if k == 'Type' and v != 'Application':
                        return
                    if k == 'Exec':
                        cmdline = unquote_exec(v)
                        if cmdline and (not os.path.isabs(cmdline[0]) or os.access(cmdline[0], os.X_OK)):
                            ans[k] = cmdline
                    elif k == 'MimeType':
                        ans[k] = frozenset(x.strip() for x in v.split(';'))
                    elif k in {'Name', 'GenericName', 'Comment', 'Icon'} or '[' in k:
                        name, lang = parse_localized_key(k)
                        if name not in ans:
                            ans[name] = {}
                        if isinstance(ans[name], type('')):
                            ans[name] = {None:ans[name]}
                        ans[name][lang] = v
                    else:
                        ans[k] = v
        if 'Exec' in ans and 'MimeType' in ans and 'Name' in ans:
            return ans

    icon_data = None

    def find_icons():
        global icon_data
        if icon_data is not None:
            return icon_data
        base_dirs = [os.path.expanduser('~/.icons')] + [
            os.path.join(b, 'icons') for b in os.environ.get(
                'XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(os.pathsep)] + [
                    '/usr/share/pixmaps']
        ans = defaultdict(list)
        sz_pat = re.compile(r'/((?:\d+x\d+)|scalable)/')
        cache_file = os.path.join(cache_dir(), 'icon-theme-cache.pickle')
        exts = {'.svg', '.png', '.xpm'}

        def read_icon_theme_dir(dirpath):
            ans = defaultdict(list)
            for path in walk(dirpath):
                bn = os.path.basename(path)
                name, ext = os.path.splitext(bn)
                if ext in exts:
                    sz = sz_pat.findall(path)
                    if sz:
                        sz = sz[-1]
                        if sz == 'scalable':
                            sz = 100000
                        else:
                            sz = int(sz.partition('x')[0])
                        idx = len(ans[name])
                        ans[name].append((-sz, idx, sz, path))
            for icons in ans.itervalues():
                icons.sort()
            return {k:(-v[0][2], v[0][3]) for k, v in ans.iteritems()}

        try:
            with open(cache_file, 'rb') as f:
                cache = cPickle.load(f)
                mtimes, cache = cache['mtimes'], cache['data']
        except Exception:
            mtimes, cache = defaultdict(int), defaultdict(dict)

        seen_dirs = set()
        changed = False

        for loc in base_dirs:
            try:
                subdirs = os.listdir(loc)
            except EnvironmentError:
                continue
            for dname in subdirs:
                d = os.path.join(loc, dname)
                if os.path.isdir(d):
                    try:
                        mtime = os.stat(d).st_mtime
                    except EnvironmentError:
                        continue
                    seen_dirs.add(d)
                    if mtime != mtimes[d]:
                        changed = True
                        try:
                            cache[d] = read_icon_theme_dir(d)
                        except Exception:
                            prints('Failed to read icon theme dir: %r with error:' % d)
                            import traceback
                            traceback.print_exc()
                        mtimes[d] = mtime
                    for name, data in cache[d].iteritems():
                        ans[name].append(data)
        for removed in set(mtimes) - seen_dirs:
            mtimes.pop(removed), cache.pop(removed)
            changed = True

        if changed:
            try:
                with open(cache_file, 'wb') as f:
                    cPickle.dump({'data':cache, 'mtimes':mtimes}, f, -1)
            except Exception:
                import traceback
                traceback.print_exc()

        for icons in ans.itervalues():
            icons.sort()
        icon_data = {k:v[0][1] for k, v in ans.iteritems()}
        return icon_data

    def localize_string(data):
        lang = canonicalize_lang(get_lang())
        return data.get(lang, data.get(None)) or ''

    def find_programs(extensions):
        extensions = {ext.lower() for ext in extensions}
        data_dirs = [os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')]
        data_dirs += (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share/:/usr/share/').split(os.pathsep)
        data_dirs = [force_unicode(x, filesystem_encoding).rstrip(os.sep) for x in data_dirs]
        data_dirs = [x for x in data_dirs if x and os.path.isdir(x)]
        desktop_files = {}
        mime_types = {guess_type('file.' + ext)[0] for ext in extensions}
        ans = []
        for base in data_dirs:
            for f in walk(os.path.join(base, 'applications')):
                if f.endswith('.desktop'):
                    bn = os.path.basename(f)
                    if f not in desktop_files:
                        desktop_files[bn] = f
        for bn, path in desktop_files.iteritems():
            try:
                data = parse_desktop_file(path)
            except Exception:
                import traceback
                traceback.print_exc()
                continue
            if data is not None and mime_types.intersection(data['MimeType']):
                icon = data.get('Icon', {}).get(None)
                if icon and not os.path.isabs(icon):
                    icon = find_icons().get(icon)
                    if icon:
                        data['Icon'] = icon
                    else:
                        data.pop('Icon')
                for k in ('Name', 'GenericName', 'Comment'):
                    val = data.get(k)
                    if val:
                        data[k] = localize_string(val)
                ans.append(data)
        ans.sort(key=lambda d:sort_key(d.get('Name')))
        return ans

    def entry_to_item(entry, parent):
        icon_path = entry.get('Icon') or I('blank.png')
        ans = QListWidgetItem(QIcon(icon_path), entry.get('Name') or _('Unknown'), parent)
        ans.setData(DESC_ROLE, entry.get('Comment') or '')
        ans.setData(ENTRY_ROLE, entry)
        comment = (entry.get('Comment') or '')
        if comment:
            comment += '\n'
        ans.setToolTip(comment + _('Command line:') + '\n' + (' '.join(entry['Exec'])))

    def choose_manually(filetype, parent):
        ans = choose_files(parent, 'choose-open-with-program-manually', _('Choose a program to open %s files') % filetype.upper(), select_only_single_file=True)
        if ans:
            ans = ans[0]
            if not os.access(ans, os.X_OK):
                return error_dialog(parent, _('Cannot execute'), _(
                    'The program %s is not an executable file') % ans, show=True)
            return {'Exec':[ans, '%f'], 'Name':os.path.basename(ans)}

    def finalize_entry(entry):
        icon_path = entry.get('Icon')
        if icon_path:
            ic = QIcon(icon_path)
            if not ic.isNull():
                pmap = ic.pixmap(48, 48)
                if not pmap.isNull():
                    entry['icon_data'] = pixmap_to_data(pmap)
        entry['MimeType'] = tuple(entry['MimeType'])
        return entry

    def entry_sort_key(entry):
        return sort_key(entry['Name'])

    def entry_to_icon_text(entry):
        data = entry.get('icon_data')
        if data is None:
            icon = QIcon(I('blank.png'))
        else:
            pmap = QPixmap()
            pmap.loadFromData(bytes(data))
            icon = QIcon(pmap)
        return icon, entry['Name']

    def entry_to_cmdline(entry, path):
        path = os.path.abspath(path)
        rmap = {
            'f':path, 'F':path, 'u':'file://'+path, 'U':'file://'+path, '%':'%',
            'i':entry.get('Icon', '%i'), 'c':entry.get('Name', ''), 'k':entry.get('desktop_file_path', ''),
        }
        def replace(match):
            char = match.group()[-1]
            repl = rmap.get(char)
            return match.group() if repl is None else repl
        sub = re.compile(r'%[fFuUdDnNickvm%]').sub
        cmd = entry['Exec']
        return cmd[:1] + [sub(replace, x) for x in cmd[1:]]

# }}}

class ChooseProgram(Dialog):  # {{{

    found = pyqtSignal()

    def __init__(self, file_type='jpeg', parent=None, prefs=oprefs):
        self.file_type = file_type
        self.programs = self.find_error = self.selected_entry = None
        self.select_manually = False
        Dialog.__init__(self, _('Choose a program'), 'choose-open-with-program-dialog', parent=parent, prefs=prefs)
        self.found.connect(self.programs_found, type=Qt.QueuedConnection)
        self.pi.startAnimation()
        t = Thread(target=self.find_programs)
        t.daemon = True
        t.start()

    def setup_ui(self):
        self.stacks = s = QStackedLayout(self)
        self.w = w = QWidget(self)
        self.w.l = l = QVBoxLayout(w)
        self.pi = pi = ProgressIndicator(self, 256)
        l.addStretch(1), l.addWidget(pi, alignment=Qt.AlignHCenter), l.addSpacing(10)
        w.la = la = QLabel(_('Gathering data, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignHCenter), l.addStretch(1)
        s.addWidget(w)

        self.w2 = w = QWidget(self)
        self.l = l = QVBoxLayout(w)
        s.addWidget(w)

        self.la = la = QLabel(_('Choose a program to open %s files') % self.file_type.upper())
        self.plist = pl = QListWidget(self)
        pl.setIconSize(QSize(48, 48)), pl.setSpacing(5)
        pl.doubleClicked.connect(self.accept)
        l.addWidget(la), l.addWidget(pl)
        la.setBuddy(pl)

        b = self.bb.addButton(_('&Browse computer for program'), self.bb.ActionRole)
        b.clicked.connect(self.manual)
        l.addWidget(self.bb)

    def sizeHint(self):
        return QSize(600, 500)

    def find_programs(self):
        try:
            self.programs = find_programs(self.file_type.split())
        except Exception:
            import traceback
            self.find_error = traceback.print_exc()
        self.found.emit()

    def programs_found(self):
        if self.find_error is not None:
            error_dialog(self, _('Error finding programs'), _(
                'Failed to find programs on your computer, click "Show details" for'
                ' more information'), det_msg=self.find_error, show=True)
            self.select_manually = True
            return self.reject()
        if not self.programs:
            self.select_manually = True
            return self.reject()
        for entry in self.programs:
            entry_to_item(entry, self.plist)
        self.stacks.setCurrentIndex(1)

    def accept(self):
        ci = self.plist.currentItem()
        if ci is not None:
            self.selected_entry = ci.data(ENTRY_ROLE)
        return Dialog.accept(self)

    def manual(self):
        self.select_manually = True
        self.reject()

oprefs.defaults['entries'] = {}

def choose_program(file_type='jpeg', parent=None, prefs=oprefs):
    d = ChooseProgram(file_type, parent, prefs)
    d.exec_()
    entry = choose_manually(file_type, parent) if d.select_manually else d.selected_entry
    if entry is not None:
        entry = finalize_entry(entry)
        entry['keyboard_shortcut'] = None
        entries = oprefs['entries']
        if file_type not in entries:
            entries[file_type] = []
        entries[file_type].append(entry)
        entries[file_type].sort(key=entry_sort_key)
        oprefs['entries'] = entries
    return entry

def populate_menu(menu, receiver, file_type):
    for entry in oprefs['entries'].get(file_type, ()):
        ac = menu.addAction(*entry_to_icon_text(entry))
        ac.triggered.connect(partial(receiver, entry))
    return menu

# }}}

if __name__ == '__main__':
    from pprint import pprint
    app = QApplication([])
    pprint(choose_program('pdf'))
    del app
