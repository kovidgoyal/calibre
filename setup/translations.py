#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil, subprocess, glob, re, time, textwrap, shlex, json, errno, hashlib, sys
from collections import defaultdict
from locale import normalize as normalize_locale
from functools import partial

from setup import Command, __appname__, __version__, require_git_master, build_cache_dir, edit_file, dump_json
from setup.parallel_build import batched_parallel_jobs
from polyglot.builtins import codepoint_to_chr, iteritems, range
is_ci = os.environ.get('CI', '').lower() == 'true'


def qt_sources():
    qtdir = os.environ.get('QT_SRC', '/usr/src/qt5/qtbase')
    j = partial(os.path.join, qtdir)
    return list(map(j, [
            'src/gui/kernel/qplatformtheme.cpp',
            'src/widgets/dialogs/qcolordialog.cpp',
            'src/widgets/dialogs/qfontdialog.cpp',
            'src/widgets/widgets/qscrollbar.cpp',
    ]))


class POT(Command):  # {{{

    description = 'Update the .pot translation template and upload it'
    TRANSLATIONS = os.path.join(os.path.dirname(Command.SRC), 'translations')
    MANUAL = os.path.join(os.path.dirname(Command.SRC), 'manual')

    def tx(self, cmd, **kw):
        kw['cwd'] = kw.get('cwd', self.TRANSLATIONS)
        if hasattr(cmd, 'format'):
            cmd = shlex.split(cmd)
        cmd = ['tx', '--traceback'] + cmd
        self.info(' '.join(cmd))
        return subprocess.check_call(cmd, **kw)

    def git(self, cmd, **kw):
        kw['cwd'] = kw.get('cwd', self.TRANSLATIONS)
        if hasattr(cmd, 'format'):
            cmd = shlex.split(cmd)
        f = getattr(subprocess, ('call' if kw.pop('use_call', False) else 'check_call'))
        return f(['git'] + cmd, **kw)

    def upload_pot(self, resource):
        self.tx(['push', '-r', 'calibre.'+resource, '-s'], cwd=self.TRANSLATIONS)

    def source_files(self):
        ans = [self.a(self.j(self.MANUAL, x)) for x in ('custom.py', 'conf.py')]
        for root, _, files in os.walk(self.j(self.SRC, __appname__)):
            for name in files:
                if name.endswith('.py'):
                    ans.append(self.a(self.j(root, name)))
        return ans

    def get_tweaks_docs(self):
        path = self.a(self.j(self.SRC, '..', 'resources', 'default_tweaks.py'))
        with open(path, 'rb') as f:
            raw = f.read().decode('utf-8')
        msgs = []
        lines = list(raw.splitlines())
        for i, line in enumerate(lines):
            if line.startswith('#:'):
                msgs.append((i, line[2:].strip()))
                j = i
                block = []
                while True:
                    j += 1
                    line = lines[j]
                    if not line.startswith('#'):
                        break
                    block.append(line[1:].strip())
                if block:
                    msgs.append((i+1, '\n'.join(block)))

        ans = []
        for lineno, msg in msgs:
            ans.append('#: %s:%d'%(path, lineno))
            slash = codepoint_to_chr(92)
            msg = msg.replace(slash, slash*2).replace('"', r'\"').replace('\n',
                    r'\n').replace('\r', r'\r').replace('\t', r'\t')
            ans.append('msgid "%s"'%msg)
            ans.append('msgstr ""')
            ans.append('')

        return '\n'.join(ans)

    def get_iso639_strings(self):
        self.info('Generating translation template for iso639')
        src = self.j(self.d(self.SRC), 'setup', 'iso_639-3.json')
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        with open(src, 'rb') as f:
            root = json.load(f)
        entries = root['639-3']
        ans = []

        def name_getter(x):
            return x.get('inverted_name') or x.get('name')

        for x in sorted(entries, key=lambda x:name_getter(x).lower()):
            name = name_getter(x)
            if name:
                ans.append(u'msgid "{}"'.format(name))
                ans.append('msgstr ""')
                ans.append('')
        pot = self.pot_header() + '\n\n' + '\n'.join(ans)
        dest = self.j(self.TRANSLATIONS, 'iso_639', 'iso_639_3.pot')
        try:
            os.makedirs(os.path.dirname(dest))
        except OSError:
            pass
        with open(dest, 'wb') as f:
            f.write(pot.encode('utf-8'))
        self.upload_pot(resource='iso639')
        self.git(['add', dest])

    def get_content_server_strings(self):
        self.info('Generating translation template for content_server')
        from calibre import walk
        from calibre.utils.rapydscript import create_pot
        files = (f for f in walk(self.j(self.SRC, 'pyj')) if f.endswith('.pyj'))
        pottext = create_pot(files).encode('utf-8')
        dest = self.j(self.TRANSLATIONS, 'content-server', 'content-server.pot')
        with open(dest, 'wb') as f:
            f.write(pottext)
        self.upload_pot(resource='content_server')
        self.git(['add', dest])

    def get_user_manual_docs(self):
        self.info('Generating translation templates for user_manual')
        base = tempfile.mkdtemp()
        subprocess.check_call([sys.executable, self.j(self.d(self.SRC), 'manual', 'build.py'), 'gettext', base])
        tbase = self.j(self.TRANSLATIONS, 'manual')
        for x in os.listdir(base):
            if not x.endswith('.pot'):
                continue
            src, dest = self.j(base, x), self.j(tbase, x)
            needs_import = not os.path.exists(dest)
            with open(src, 'rb') as s, open(dest, 'wb') as d:
                shutil.copyfileobj(s, d)
            bname = os.path.splitext(x)[0]
            slug = 'user_manual_' + bname
            if needs_import:
                self.tx(['set', '-r', 'calibre.' + slug, '--source', '-l', 'en', '-t', 'PO', dest])
                with open(self.j(self.d(tbase), '.tx/config'), 'r+b') as f:
                    lines = f.read().decode('utf-8').splitlines()
                    for i in range(len(lines)):
                        line = lines[i].strip()
                        if line == '[calibre.%s]' % slug:
                            lines.insert(i+1, 'file_filter = manual/<lang>/%s.po' % bname)
                            f.seek(0), f.truncate(), f.write('\n'.join(lines).encode('utf-8'))
                            break
                    else:
                        raise SystemExit(f'Failed to add file_filter for {slug=} to config file')
                self.git('add .tx/config')
            self.upload_pot(resource=slug)
            self.git(['add', dest])
        shutil.rmtree(base)

    def get_website_strings(self):
        self.info('Generating translation template for website')
        self.wn_path = os.path.expanduser('~/work/srv/main/static/generate.py')
        data = subprocess.check_output([self.wn_path, '--pot', '/tmp/wn'])
        data = json.loads(data)

        def do(name):
            messages = data[name]
            bdir = os.path.join(self.TRANSLATIONS, name)
            if not os.path.exists(bdir):
                os.makedirs(bdir)
            pot = os.path.abspath(os.path.join(bdir, name + '.pot'))
            with open(pot, 'wb') as f:
                f.write(self.pot_header().encode('utf-8'))
                f.write(b'\n')
                f.write('\n'.join(messages).encode('utf-8'))
            self.upload_pot(resource=name)
            self.git(['add', pot])

        do('website')
        do('changelog')

    def pot_header(self, appname=__appname__, version=__version__):
        return textwrap.dedent('''\
        # Translation template file..
        # Copyright (C) %(year)s Kovid Goyal
        # Kovid Goyal <kovid@kovidgoyal.net>, %(year)s.
        #
        msgid ""
        msgstr ""
        "Project-Id-Version: %(appname)s %(version)s\\n"
        "POT-Creation-Date: %(time)s\\n"
        "PO-Revision-Date: %(time)s\\n"
        "Last-Translator: Automatically generated\\n"
        "Language-Team: LANGUAGE\\n"
        "MIME-Version: 1.0\\n"
        "Report-Msgid-Bugs-To: https://bugs.launchpad.net/calibre\\n"
        "Plural-Forms: nplurals=INTEGER; plural=EXPRESSION;\\n"
        "Content-Type: text/plain; charset=UTF-8\\n"
        "Content-Transfer-Encoding: 8bit\\n"

        ''')%dict(appname=appname, version=version,
                year=time.strftime('%Y'),
                time=time.strftime('%Y-%m-%d %H:%M+%Z'))

    def run(self, opts):
        if not is_ci:
            require_git_master()
        self.get_iso639_strings()
        if not is_ci:
            self.get_website_strings()
        self.get_content_server_strings()
        self.get_user_manual_docs()
        files = self.source_files()
        qt_inputs = qt_sources()
        pot_header = self.pot_header()

        with tempfile.NamedTemporaryFile() as fl:
            fl.write('\n'.join(files).encode('utf-8'))
            fl.flush()
            out = tempfile.NamedTemporaryFile(suffix='.pot', delete=False)
            out.close()
            self.info('Creating translations template...')
            subprocess.check_call(['xgettext', '-f', fl.name,
                '--default-domain=calibre', '-o', out.name, '-L', 'Python',
                '--from-code=UTF-8', '--sort-by-file', '--omit-header',
                '--no-wrap', '-k__', '--add-comments=NOTE:',
                ])
            subprocess.check_call(['xgettext', '-j',
                '--default-domain=calibre', '-o', out.name,
                '--from-code=UTF-8', '--sort-by-file', '--omit-header',
                                   '--no-wrap', '-kQT_TRANSLATE_NOOP:2', '-ktr', '-ktranslate:2',
                ] + qt_inputs)

            with open(out.name, 'rb') as f:
                src = f.read().decode('utf-8')
            os.remove(out.name)
            src = pot_header + '\n' + src
            src += '\n\n' + self.get_tweaks_docs()
            bdir = os.path.join(self.TRANSLATIONS, __appname__)
            if not os.path.exists(bdir):
                os.makedirs(bdir)
            pot = os.path.join(bdir, 'main.pot')
            # Workaround for bug in xgettext:
            # https://savannah.gnu.org/bugs/index.php?41668
            src = re.sub(r'#, python-brace-format\s+msgid ""\s+.*<code>{0:</code>',
                   lambda m: m.group().replace('python-brace', 'no-python-brace'), src)
            with open(pot, 'wb') as f:
                f.write(src.encode('utf-8'))
            self.info('Translations template:', os.path.abspath(pot))
            self.upload_pot(resource='main')
            self.git(['add', os.path.abspath(pot)])

        if not is_ci and self.git('diff-index --cached --quiet --ignore-submodules HEAD --', use_call=True) != 0:
            self.git(['commit', '-m', 'Updated translation templates'])
            self.git('push')

        return pot
# }}}


class Translations(POT):  # {{{
    description='''Compile the translations'''
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'locales')

    @property
    def cache_dir(self):
        ans = self.j(build_cache_dir(), 'translations')
        if not hasattr(self, 'cache_dir_created'):
            self.cache_dir_created = True
            try:
                os.mkdir(ans)
            except EnvironmentError as err:
                if err.errno != errno.EEXIST:
                    raise
        return ans

    def cache_name(self, f):
        f = os.path.relpath(f, self.d(self.SRC))
        return f.replace(os.sep, '.').replace('/', '.').lstrip('.')

    def read_cache(self, f):
        cname = self.cache_name(f)
        try:
            with open(self.j(self.cache_dir, cname), 'rb') as f:
                data = f.read()
                return data[:20], data[20:]
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        return None, None

    def write_cache(self, data, h, f):
        cname = self.cache_name(f)
        assert len(h) == 20
        with open(self.j(self.cache_dir, cname), 'wb') as f:
            f.write(h), f.write(data)

    def po_files(self):
        return glob.glob(os.path.join(self.TRANSLATIONS, __appname__, '*.po'))

    def mo_file(self, po_file):
        locale = os.path.splitext(os.path.basename(po_file))[0]
        return locale, os.path.join(self.DEST, locale, 'messages.mo')

    def run(self, opts):
        self.compile_main_translations()
        self.compile_content_server_translations()
        self.freeze_locales()
        self.compile_user_manual_translations()
        self.compile_website_translations()
        self.compile_changelog_translations()

    def compile_group(self, files, handle_stats=None, file_ok=None, action_per_file=None):
        ok_files = []
        hashmap = {}

        def stats_cache(src, data=None):
            cname = self.cache_name(src) + '.stats.json'
            with open(self.j(self.cache_dir, cname), ('rb' if data is None else 'wb')) as f:
                if data is None:
                    return json.loads(f.read())
                data = json.dumps(data)
                if not isinstance(data, bytes):
                    data = data.encode('utf-8')
                f.write(data)

        for src, dest in files:
            base = os.path.dirname(dest)
            if not os.path.exists(base):
                os.makedirs(base)
            data, h = self.hash_and_data(src)
            current_hash = h.digest()
            saved_hash, saved_data = self.read_cache(src)
            if current_hash == saved_hash:
                with open(dest, 'wb') as d:
                    d.write(saved_data)
                    if handle_stats is not None:
                        handle_stats(src, stats_cache(src))
            else:
                if file_ok is None or file_ok(data, src):
                    # self.info('\t' + os.path.relpath(src, self.j(self.d(self.SRC), 'translations')))
                    ok_files.append((src, dest))
                    hashmap[src] = current_hash
            if action_per_file is not None:
                action_per_file(src)

        self.info(f'\tCompiling {len(ok_files)} files')
        items = []
        results = batched_parallel_jobs(
            [sys.executable, self.j(self.SRC, 'calibre', 'translations', 'msgfmt.py'), 'STDIN'],
            ok_files)
        for (src, dest), nums in zip(ok_files, results):
            items.append((src, dest, nums))

        for (src, dest, nums) in items:
            self.write_cache(open(dest, 'rb').read(), hashmap[src], src)
            stats_cache(src, nums)
            if handle_stats is not None:
                handle_stats(src, nums)

    def auto_fix_iso639_files(self, files):

        class Fix(object):

            def __init__(self):
                self.seen = set()
                self.bad = set()
                self.msgid = None

            def __call__(self, match):
                if match.group(1) == 'msgid':
                    self.msgid = match.group(2)
                    return match.group()
                msgstr = match.group(2)
                if msgstr:
                    if msgstr in self.seen:
                        if self.msgid == msgstr:
                            self.bad.add(msgstr)
                            return match.group()
                        self.seen.add(self.msgid)
                        return 'msgstr "{}"'.format(self.msgid)
                    self.seen.add(msgstr)
                return match.group()

        class Fix2(object):

            def __init__(self, fix1):
                self.bad = fix1.bad
                self.msgid = None

            def __call__(self, match):
                if match.group(1) == 'msgid':
                    self.msgid = match.group(2)
                    return match.group()
                msgstr = match.group(2)
                if msgstr:
                    if msgstr and msgstr in self.bad:
                        self.bad.discard(msgstr)
                        return 'msgstr "{}"'.format(self.msgid)
                return match.group()

        for (po_path, mo_path) in files:
            with open(po_path, 'r+b') as f:
                raw = f.read().decode('utf-8')
                f.seek(0)
                fx = Fix()
                nraw, num = re.subn(r'^(msgid|msgstr)\s+"(.*?)"', fx, raw, flags=re.M)
                nraw, nnum = re.subn(r'^(msgid|msgstr)\s+"(.*?)"', Fix2(fx), nraw, flags=re.M)
                if num + nnum > 0:
                    f.truncate()
                    f.write(nraw.encode('utf-8'))
        raise SystemExit(1)

    def compile_main_translations(self):
        l = {}
        lc_dataf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lc_data.py')
        exec(compile(open(lc_dataf, 'rb').read(), lc_dataf, 'exec'), l, l)
        lcdata = {k:{k1:v1 for k1, v1 in v} for k, v in l['data']}
        self.iso639_errors = []
        self.info('Compiling main UI translation files...')
        fmap = {f:self.mo_file(f) for f in self.po_files()}
        files = [(f, fmap[f][1]) for f in self.po_files()]

        def action_per_file(f):
            locale, dest = fmap[f]
            ln = normalize_locale(locale).partition('.')[0]
            if ln in lcdata:
                ld = lcdata[ln]
                lcdest = self.j(self.d(dest), 'lcdata.calibre_msgpack')
                from calibre.utils.serialize import msgpack_dumps
                with open(lcdest, 'wb') as lcf:
                    lcf.write(msgpack_dumps(ld))

        stats = {}

        def handle_stats(f, nums):
            trans = nums[0]
            total = trans if len(nums) == 1 else (trans + nums[1])
            locale = fmap[f][0]
            stats[locale] = min(1.0, float(trans)/total)

        self.compile_group(files, handle_stats=handle_stats, action_per_file=action_per_file)
        self.info('Compiling ISO639 files...')

        files = []
        skip_iso = {
            'en_GB', 'en_CA', 'en_AU', 'si', 'ur', 'sc', 'ltg', 'nds',
            'te', 'yi', 'fo', 'sq', 'ast', 'ml', 'ku', 'fr_CA', 'him',
            'jv', 'ka', 'fur', 'ber', 'my', 'fil', 'hy', 'ug'}
        for f, (locale, dest) in iteritems(fmap):
            iscpo = {'bn':'bn_IN', 'zh_HK':'zh_CN'}.get(locale, locale)
            iso639 = self.j(self.TRANSLATIONS, 'iso_639', '%s.po'%iscpo)
            if os.path.exists(iso639):
                files.append((iso639, self.j(self.d(dest), 'iso639.mo')))
            elif locale not in skip_iso:
                self.warn('No ISO 639 translations for locale:', locale)
        # self.auto_fix_iso639_files(files)
        self.compile_group(files, file_ok=self.check_iso639)

        if self.iso639_errors:
            for err in self.iso639_errors:
                print(err)
            raise SystemExit(1)

        dest = self.stats
        base = self.d(dest)
        try:
            os.mkdir(base)
        except EnvironmentError as err:
            if err.errno != errno.EEXIST:
                raise
        from calibre.utils.serialize import msgpack_dumps
        with open(dest, 'wb') as f:
            f.write(msgpack_dumps(stats))

    def hash_and_data(self, f):
        with open(f, 'rb') as s:
            data = s.read()
        h = hashlib.sha1(data)
        h.update(f.encode('utf-8'))
        return data, h

    def compile_content_server_translations(self):
        self.info('Compiling content-server translations')
        from calibre.utils.rapydscript import msgfmt
        from calibre.utils.zipfile import ZipFile, ZIP_DEFLATED, ZipInfo, ZIP_STORED
        with ZipFile(self.j(self.RESOURCES, 'content-server', 'locales.zip'), 'w', ZIP_DEFLATED) as zf:
            for src in glob.glob(os.path.join(self.TRANSLATIONS, 'content-server', '*.po')):
                data, h = self.hash_and_data(src)
                current_hash = h.digest()
                saved_hash, saved_data = self.read_cache(src)
                if current_hash == saved_hash:
                    raw = saved_data
                else:
                    # self.info('\tParsing ' + os.path.basename(src))
                    raw = None
                    po_data = data.decode('utf-8')
                    data = json.loads(msgfmt(po_data))
                    translated_entries = {k:v for k, v in iteritems(data['entries']) if v and sum(map(len, v))}
                    data[u'entries'] = translated_entries
                    data[u'hash'] = h.hexdigest()
                    cdata = b'{}'
                    if translated_entries:
                        raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
                        if isinstance(raw, type(u'')):
                            raw = raw.encode('utf-8')
                        cdata = raw
                    self.write_cache(cdata, current_hash, src)
                if raw:
                    zi = ZipInfo(os.path.basename(src).rpartition('.')[0])
                    zi.compress_type = ZIP_STORED if is_ci else ZIP_DEFLATED
                    zf.writestr(zi, raw)

    def check_iso639(self, raw, path):
        from calibre.utils.localization import langnames_to_langcodes
        rmap = {}
        msgid = None
        has_errors = False
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        for match in re.finditer(r'^(msgid|msgstr)\s+"(.*?)"', raw, re.M):
            if match.group(1) == 'msgid':
                msgid = match.group(2)
            else:
                msgstr = match.group(2)
                if not msgstr:
                    continue
                omsgid = rmap.get(msgstr, None)
                if omsgid is not None:
                    cm = langnames_to_langcodes([omsgid, msgid])
                    if cm[msgid] and cm[omsgid] and cm[msgid] != cm[omsgid]:
                        has_errors = True
                        self.iso639_errors.append('In file %s the name %s is used as translation for both %s and %s' % (
                            os.path.basename(path), msgstr, msgid, rmap[msgstr]))
                    # raise SystemExit(1)
                rmap[msgstr] = msgid
        return not has_errors

    def freeze_locales(self):
        zf = self.DEST + '.zip'
        from calibre import CurrentDir
        from calibre.utils.zipfile import ZipFile, ZIP_DEFLATED
        with ZipFile(zf, 'w', ZIP_DEFLATED) as zf:
            with CurrentDir(self.DEST):
                zf.add_dir('.')
        shutil.rmtree(self.DEST)

    @property
    def stats(self):
        return self.j(self.d(self.DEST), 'stats.calibre_msgpack')

    def _compile_website_translations(self, name='website', threshold=50):
        from calibre.utils.zipfile import ZipFile, ZipInfo, ZIP_STORED
        from calibre.ptempfile import TemporaryDirectory
        from calibre.utils.localization import get_language, translator_for_lang
        self.info('Compiling', name, 'translations...')
        srcbase = self.j(self.d(self.SRC), 'translations', name)
        if not os.path.exists(srcbase):
            os.makedirs(srcbase)
        fmap = {}
        files = []
        stats = {}
        done = []

        def handle_stats(src, nums):
            locale = fmap[src]
            trans = nums[0]
            total = trans if len(nums) == 1 else (trans + nums[1])
            stats[locale] = int(round(100 * trans / total))

        with TemporaryDirectory() as tdir, ZipFile(self.j(srcbase, 'locales.zip'), 'w', ZIP_STORED) as zf:
            for f in os.listdir(srcbase):
                if f.endswith('.po'):
                    l = f.partition('.')[0]
                    pf = l.split('_')[0]
                    if pf in {'en'}:
                        continue
                    d = os.path.join(tdir, l + '.mo')
                    f = os.path.join(srcbase, f)
                    fmap[f] = l
                    files.append((f, d))
            self.compile_group(files, handle_stats=handle_stats)

            for locale, translated in iteritems(stats):
                if translated >= 50:
                    with open(os.path.join(tdir, locale + '.mo'), 'rb') as f:
                        raw = f.read()
                    zi = ZipInfo(os.path.basename(f.name))
                    zi.compress_type = ZIP_STORED
                    zf.writestr(zi, raw)
                    done.append(locale)
            dl = done + ['en']

            lang_names = {}
            for l in dl:
                translator = translator_for_lang(l)['translator']
                t = translator.gettext
                t = partial(get_language, gettext_func=t)
                lang_names[l] = {x: t(x) for x in dl}
            zi = ZipInfo('lang-names.json')
            zi.compress_type = ZIP_STORED
            zf.writestr(zi, json.dumps(lang_names, ensure_ascii=False).encode('utf-8'))
            return done

    def compile_website_translations(self):
        done = self._compile_website_translations()
        dest = self.j(self.d(self.stats), 'website-languages.txt')
        data = ' '.join(sorted(done))
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        with open(dest, 'wb') as f:
            f.write(data)

    def compile_changelog_translations(self):
        self._compile_website_translations('changelog', 0)

    def compile_user_manual_translations(self):
        self.info('Compiling user manual translations...')
        srcbase = self.j(self.d(self.SRC), 'translations', 'manual')
        destbase = self.j(self.d(self.SRC), 'manual', 'locale')
        complete = {}
        all_stats = defaultdict(lambda : {'translated': 0, 'untranslated': 0})
        files = []
        for x in os.listdir(srcbase):
            q = self.j(srcbase, x)
            if not os.path.isdir(q):
                continue
            dest = self.j(destbase, x, 'LC_MESSAGES')
            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            for po in os.listdir(q):
                if not po.endswith('.po'):
                    continue
                mofile = self.j(dest, po.rpartition('.')[0] + '.mo')
                files.append((self.j(q, po), mofile))

        def handle_stats(src, nums):
            locale = self.b(self.d(src))
            stats = all_stats[locale]
            stats['translated'] += nums[0]
            if len(nums) > 1:
                stats['untranslated'] += nums[1]

        self.compile_group(files, handle_stats=handle_stats)
        for locale, stats in iteritems(all_stats):
            dump_json(stats, self.j(srcbase, locale, 'stats.json'))
            total = stats['translated'] + stats['untranslated']
            # Raise the 30% threshold in the future
            if total and (stats['translated'] / float(total)) > 0.3:
                complete[locale] = stats
        dump_json(complete, self.j(destbase, 'completed.json'))

    def clean(self):
        if os.path.exists(self.stats):
            os.remove(self.stats)
        zf = self.DEST + '.zip'
        if os.path.exists(zf):
            os.remove(zf)
        destbase = self.j(self.d(self.SRC), 'manual', 'locale')
        if os.path.exists(destbase):
            shutil.rmtree(destbase)
        shutil.rmtree(self.cache_dir)

# }}}


class GetTranslations(Translations):  # {{{

    description = 'Get updated translations from Transifex'

    @property
    def is_modified(self):
        return bool(subprocess.check_output('git status --porcelain'.split(), cwd=self.TRANSLATIONS))

    def add_options(self, parser):
        parser.add_option('-e', '--check-for-errors', default=False, action='store_true',
                          help='Check for errors in .po files')

    def run(self, opts):
        require_git_master()
        if opts.check_for_errors:
            self.check_all()
            return
        self.tx('pull -a --parallel --no-interactive')
        if not self.is_modified:
            self.info('No translations were updated')
            return
        self.upload_to_vcs()
        self.check_all()

    def check_all(self):
        self.check_for_errors()
        self.check_for_user_manual_errors()
        if self.is_modified:
            self.upload_to_vcs('Fixed translations')

    def check_for_user_manual_errors(self):
        self.info('Checking user manual translations...')
        srcbase = self.j(self.d(self.SRC), 'translations', 'manual')
        import polib
        changes = defaultdict(set)
        for lang in os.listdir(srcbase):
            if lang.startswith('en_') or lang == 'en':
                continue
            q = self.j(srcbase, lang)
            if not os.path.isdir(q):
                continue
            for po in os.listdir(q):
                if not po.endswith('.po'):
                    continue
                f = polib.pofile(os.path.join(q, po))
                changed = False
                for entry in f.translated_entries():
                    if '`generated/en/' in entry.msgstr:
                        changed = True
                        entry.msgstr = entry.msgstr.replace('`generated/en/', '`generated/' + lang + '/')
                        bname = os.path.splitext(po)[0]
                        slug = 'user_manual_' + bname
                        changes[slug].add(lang)
                if changed:
                    f.save()
        for slug, languages in iteritems(changes):
            print('Pushing fixes for languages: %s in %s' % (', '.join(languages), slug))
            self.tx('push -r calibre.%s -t -l %s' % (slug, ','.join(languages)))

    def check_for_errors(self):
        self.info('Checking for errors in .po files...')
        groups = 'calibre content-server website'.split()
        for group in groups:
            self.check_group(group)
        self.check_website()
        for group in groups:
            self.push_fixes(group)

    def push_fixes(self, group):
        languages = set()
        for line in subprocess.check_output('git status --porcelain'.split(), cwd=self.TRANSLATIONS).decode('utf-8').splitlines():
            parts = line.strip().split()
            if len(parts) > 1 and 'M' in parts[0] and parts[-1].startswith(group + '/') and parts[-1].endswith('.po'):
                languages.add(os.path.basename(parts[-1]).partition('.')[0])
        if languages:
            pot = 'main' if group == 'calibre' else group.replace('-', '_')
            print('Pushing fixes for %s.pot languages: %s' % (pot, ', '.join(languages)))
            self.tx('push -r calibre.{} -t -l '.format(pot) + ','.join(languages))

    def check_group(self, group):
        files = glob.glob(os.path.join(self.TRANSLATIONS, group, '*.po'))
        cmd = ['msgfmt', '-o', os.devnull, '--check-format']
        # Disabled because too many such errors, and not that critical anyway
        # if group == 'calibre':
        #     cmd += ['--check-accelerators=&']

        def check(f):
            p = subprocess.Popen(cmd + [f], stderr=subprocess.PIPE)
            errs = p.stderr.read()
            p.wait()
            return errs

        def check_for_control_chars(f):
            with open(f, 'rb') as f:
                raw = f.read().decode('utf-8')
            pat = re.compile(type(u'')(r'[\0-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]'))
            errs = []
            for i, line in enumerate(raw.splitlines()):
                if pat.search(line) is not None:
                    errs.append('There are ASCII control codes on line number: {}'.format(i + 1))
            return '\n'.join(errs)

        for f in files:
            errs = check(f)
            if errs:
                print(f)
                print(errs)
                edit_file(f)
                if check(f):
                    raise SystemExit('Aborting as not all errors were fixed')
            errs = check_for_control_chars(f)
            if errs:
                print(f, 'has ASCII control codes in it')
                print(errs)
                raise SystemExit(1)

    def check_website(self):
        errors = os.path.join(tempfile.gettempdir(), 'calibre-translation-errors')
        if os.path.exists(errors):
            shutil.rmtree(errors)
        os.mkdir(errors)
        tpath = self.j(self.TRANSLATIONS, 'website')
        pofilter = ('pofilter', '-i', tpath, '-o', errors, '-t', 'xmltags')
        subprocess.check_call(pofilter)
        errfiles = glob.glob(errors+os.sep+'*.po')
        if errfiles:
            subprocess.check_call(['vim', '-f', '-p', '--']+errfiles)
            for f in errfiles:
                with open(f, 'r+b') as f:
                    raw = f.read()
                    raw = re.sub(rb'# \(pofilter\).*', b'', raw)
                    f.seek(0)
                    f.truncate()
                    f.write(raw)

            subprocess.check_call(['pomerge', '-t', tpath, '-i', errors, '-o', tpath])

    def upload_to_vcs(self, msg=None):
        self.info('Uploading updated translations to version control')
        cc = partial(subprocess.check_call, cwd=self.TRANSLATIONS)
        cc('git add */*.po'.split())
        cc('git commit -am'.split() + [msg or 'Updated translations'])
        cc('git push'.split())

# }}}


class ISO639(Command):  # {{{

    description = 'Compile language code maps for performance'
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'iso639.calibre_msgpack')

    def run(self, opts):
        src = self.j(self.d(self.SRC), 'setup', 'iso_639-3.json')
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        dest = self.DEST
        base = self.d(dest)
        if not os.path.exists(base):
            os.makedirs(base)
        if not self.newer(dest, [src, __file__]):
            self.info('Packed code is up to date')
            return
        self.info('Packing ISO-639 codes to', dest)
        with open(src, 'rb') as f:
            root = json.load(f)
        entries = root['639-3']
        by_2 = {}
        by_3 = {}
        m2to3 = {}
        m3to2 = {}
        nm = {}
        codes2, codes3 = set(), set()
        unicode_type = type(u'')
        for x in entries:
            two = x.get('alpha_2')
            if two:
                two = unicode_type(two)
            threeb = x.get('alpha_3')
            if threeb:
                threeb = unicode_type(threeb)
            if threeb is None:
                continue
            name = x.get('inverted_name') or x.get('name')
            if name:
                name = unicode_type(name)
            if not name or name[0] in '!~=/\'"':
                continue

            if two is not None:
                by_2[two] = name
                codes2.add(two)
                m2to3[two] = threeb
                m3to2[threeb] = two
            codes3.add(threeb)
            by_3[threeb] = name
            base_name = name.lower()
            nm[base_name] = threeb

        x = {u'by_2':by_2, u'by_3':by_3, u'codes2':codes2,
                u'codes3':codes3, u'2to3':m2to3,
                u'3to2':m3to2, u'name_map':nm}
        from calibre.utils.serialize import msgpack_dumps
        with open(dest, 'wb') as f:
            f.write(msgpack_dumps(x))

    def clean(self):
        if os.path.exists(self.DEST):
            os.remove(self.DEST)

# }}}


class ISO3166(ISO639):  # {{{

    description = 'Compile country code maps for performance'
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'iso3166.calibre_msgpack')

    def run(self, opts):
        src = self.j(self.d(self.SRC), 'setup', 'iso_3166-1.json')
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        dest = self.DEST
        base = self.d(dest)
        if not os.path.exists(base):
            os.makedirs(base)
        if not self.newer(dest, [src, __file__]):
            self.info('Packed code is up to date')
            return
        self.info('Packing ISO-3166 codes to', dest)
        with open(src, 'rb') as f:
            db = json.load(f)
        codes = set()
        three_map = {}
        name_map = {}
        unicode_type = type(u'')
        for x in db['3166-1']:
            two = x.get('alpha_2')
            if two:
                two = unicode_type(two)
            codes.add(two)
            name_map[two] = x.get('name')
            if name_map[two]:
                name_map[two] = unicode_type(name_map[two])
            three = x.get('alpha_3')
            if three:
                three_map[unicode_type(three)] = two
        x = {u'names':name_map, u'codes':frozenset(codes), u'three_map':three_map}
        from calibre.utils.serialize import msgpack_dumps
        with open(dest, 'wb') as f:
            f.write(msgpack_dumps(x))
# }}}
