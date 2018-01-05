#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil, subprocess, glob, re, time, textwrap, cPickle, shlex, json, errno, hashlib, sys
from collections import defaultdict
from locale import normalize as normalize_locale
from functools import partial

from setup import Command, __appname__, __version__, require_git_master, build_cache_dir, edit_file
from setup.parallel_build import parallel_check_output
is_ci = os.environ.get('CI', '').lower() == 'true'


def qt_sources():
    qtdir = '/usr/src/qt5'
    j = partial(os.path.join, qtdir)
    return list(map(j, [
            'qtbase/src/gui/kernel/qplatformtheme.cpp',
            'qtbase/src/widgets/dialogs/qcolordialog.cpp',
            'qtbase/src/widgets/dialogs/qfontdialog.cpp',
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
            slash = unichr(92)
            msg = msg.replace(slash, slash*2).replace('"', r'\"').replace('\n',
                    r'\n').replace('\r', r'\r').replace('\t', r'\t')
            ans.append('msgid "%s"'%msg)
            ans.append('msgstr ""')
            ans.append('')

        return '\n'.join(ans)

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
        subprocess.check_call(['calibre-debug', self.j(self.d(self.SRC), 'manual', 'build.py'), 'gettext', base])
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
                    lines = f.read().splitlines()
                    for i in xrange(len(lines)):
                        line = lines[i]
                        if line == '[calibre.%s]' % slug:
                            lines.insert(i+1, 'file_filter = manual/<lang>/%s.po' % bname)
                            f.seek(0), f.truncate(), f.write('\n'.join(lines))
                            break
                    else:
                        self.info('Failed to add file_filter to config file')
                        raise SystemExit(1)
                self.git('add .tx/config')
            self.upload_pot(resource=slug)
            self.git(['add', dest])
        shutil.rmtree(base)

    def get_website_strings(self):
        self.info('Generating translation template for website')
        self.wn_path = os.path.expanduser('~/work/srv/main/static/generate.py')
        data = subprocess.check_output([self.wn_path, '--pot'])
        bdir = os.path.join(self.TRANSLATIONS, 'website')
        if not os.path.exists(bdir):
            os.makedirs(bdir)
        pot = os.path.join(bdir, 'website.pot')
        with open(pot, 'wb') as f:
            f.write(self.pot_header().encode('utf-8'))
            f.write(b'\n')
            f.write(data)
        self.info('Website translations:', os.path.abspath(pot))
        self.upload_pot(resource='website')
        self.git(['add', os.path.abspath(pot)])

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
        require_git_master()
        self.get_website_strings()
        self.get_content_server_strings()
        self.get_user_manual_docs()
        files = self.source_files()
        qt_inputs = qt_sources()
        pot_header = self.pot_header()

        with tempfile.NamedTemporaryFile() as fl:
            fl.write('\n'.join(files))
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
                src = f.read()
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
                f.write(src)
            self.info('Translations template:', os.path.abspath(pot))
            self.upload_pot(resource='main')
            self.git(['add', os.path.abspath(pot)])

        if self.git('diff-index --cached --quiet --ignore-submodules HEAD --', use_call=True) != 0:
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

    def compile_group(self, files, handle_stats=None, file_ok=None, action_per_file=None):
        from calibre.constants import islinux
        jobs, ok_files = [], []
        hashmap = {}

        def stats_cache(src, data=None):
            cname = self.cache_name(src) + '.stats.json'
            with open(self.j(self.cache_dir, cname), ('rb' if data is None else 'wb')) as f:
                if data is None:
                    return json.load(f)
                json.dump(data, f)

        for src, dest in files:
            base = os.path.dirname(dest)
            if not os.path.exists(base):
                os.makedirs(base)
            data, current_hash = self.hash_and_data(src)
            saved_hash, saved_data = self.read_cache(src)
            if current_hash == saved_hash:
                with open(dest, 'wb') as d:
                    d.write(saved_data)
                    if handle_stats is not None:
                        handle_stats(src, stats_cache(src))
            else:
                if file_ok is None or file_ok(data, src):
                    self.info('\t' + os.path.relpath(src, self.j(self.d(self.SRC), 'translations')))
                    if islinux:
                        msgfmt = ['msgfmt']
                    else:
                        msgfmt = [sys.executable, self.j(self.SRC, 'calibre', 'translations', 'msgfmt.py')]
                    jobs.append(msgfmt + ['--statistics', '-o', dest, src])
                    ok_files.append((src, dest))
                    hashmap[src] = current_hash
            if action_per_file is not None:
                action_per_file(src)

        for (src, dest), line in zip(ok_files, parallel_check_output(jobs, self.info)):
            self.write_cache(open(dest, 'rb').read(), hashmap[src], src)
            nums = tuple(map(int, re.findall(r'\d+', line)))
            stats_cache(src, nums)
            if handle_stats is not None:
                handle_stats(src, nums)

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
                lcdest = self.j(self.d(dest), 'lcdata.pickle')
                with open(lcdest, 'wb') as lcf:
                    lcf.write(cPickle.dumps(ld, -1))

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
        for f, (locale, dest) in fmap.iteritems():
            iscpo = {'bn':'bn_IN', 'zh_HK':'zh_CN'}.get(locale, locale)
            iso639 = self.j(self.TRANSLATIONS, 'iso_639', '%s.po'%iscpo)
            if os.path.exists(iso639):
                files.append((iso639, self.j(self.d(dest), 'iso639.mo')))
            elif locale not in skip_iso:
                self.warn('No ISO 639 translations for locale:', locale)
        self.compile_group(files, file_ok=self.check_iso639)

        if self.iso639_errors:
            for err in self.iso639_errors:
                print (err)
            raise SystemExit(1)

        dest = self.stats
        base = self.d(dest)
        try:
            os.mkdir(base)
        except EnvironmentError as err:
            if err.errno != errno.EEXIST:
                raise
        cPickle.dump(stats, open(dest, 'wb'), -1)

    def hash_and_data(self, f):
        with open(f, 'rb') as s:
            data = s.read()
        h = hashlib.sha1(data)
        h.update(f.encode('utf-8'))
        return data, h.digest()

    def compile_content_server_translations(self):
        self.info('Compiling content-server translations')
        from calibre.utils.rapydscript import msgfmt
        from calibre.utils.zipfile import ZipFile, ZIP_DEFLATED, ZipInfo, ZIP_STORED
        with ZipFile(self.j(self.RESOURCES, 'content-server', 'locales.zip'), 'w', ZIP_DEFLATED) as zf:
            for src in glob.glob(os.path.join(self.TRANSLATIONS, 'content-server', '*.po')):
                data, current_hash = self.hash_and_data(src)
                saved_hash, saved_data = self.read_cache(src)
                if current_hash == saved_hash:
                    raw = saved_data
                else:
                    self.info('\tParsing ' + os.path.basename(src))
                    raw = None
                    po_data = data.decode('utf-8')
                    data = json.loads(msgfmt(po_data))
                    translated_entries = {k:v for k, v in data['entries'].iteritems() if v and sum(map(len, v))}
                    data['entries'] = translated_entries
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
        return self.j(self.d(self.DEST), 'stats.pickle')

    def compile_website_translations(self):
        from calibre.utils.zipfile import ZipFile, ZipInfo, ZIP_STORED
        from calibre.ptempfile import TemporaryDirectory
        from calibre.utils.localization import get_iso639_translator, get_language, get_iso_language
        self.info('Compiling website translations...')
        srcbase = self.j(self.d(self.SRC), 'translations', 'website')
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

            for locale, translated in stats.iteritems():
                if translated >= 20:
                    with open(os.path.join(tdir, locale + '.mo'), 'rb') as f:
                        raw = f.read()
                    zi = ZipInfo(os.path.basename(f.name))
                    zi.compress_type = ZIP_STORED
                    zf.writestr(zi, raw)
                    done.append(locale)
            dl = done + ['en']

            lang_names = {}
            for l in dl:
                if l == 'en':
                    t = get_language
                else:
                    t = get_iso639_translator(l).ugettext
                    t = partial(get_iso_language, t)
                lang_names[l] = {x: t(x) for x in dl}
            zi = ZipInfo('lang-names.json')
            zi.compress_type = ZIP_STORED
            zf.writestr(zi, json.dumps(lang_names, ensure_ascii=False).encode('utf-8'))
        dest = self.j(self.d(self.stats), 'website-languages.txt')
        with open(dest, 'wb') as f:
            f.write(' '.join(sorted(done)))

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
        for locale, stats in all_stats.iteritems():
            with open(self.j(srcbase, locale, 'stats.json'), 'wb') as f:
                json.dump(stats, f)
            total = stats['translated'] + stats['untranslated']
            # Raise the 30% threshold in the future
            if total and (stats['translated'] / float(total)) > 0.3:
                complete[locale] = stats
        with open(self.j(destbase, 'completed.json'), 'wb') as f:
            json.dump(complete, f, indent=True, sort_keys=True)

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
        self.tx('pull -a')
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
        for slug, languages in changes.iteritems():
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
            raw = open(f, 'rb').read().decode('utf-8')
            pat = re.compile(ur'[\0-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]')
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
                    raw = re.sub(r'# \(pofilter\).*', '', raw)
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
            'iso639.pickle')

    def run(self, opts):
        src = self.j(self.d(self.SRC), 'setup', 'iso_639_3.xml')
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        dest = self.DEST
        base = self.d(dest)
        if not os.path.exists(base):
            os.makedirs(base)
        if not self.newer(dest, [src, __file__]):
            self.info('Pickled code is up to date')
            return
        self.info('Pickling ISO-639 codes to', dest)
        from lxml import etree
        root = etree.fromstring(open(src, 'rb').read())
        by_2 = {}
        by_3b = {}
        by_3t = {}
        m2to3 = {}
        m3to2 = {}
        m3bto3t = {}
        nm = {}
        codes2, codes3t, codes3b = set(), set(), set()
        for x in root.xpath('//iso_639_3_entry'):
            two = x.get('part1_code', None)
            threet = x.get('id')
            threeb = x.get('part2_code', None)
            if threeb is None:
                # Only recognize languages in ISO-639-2
                continue
            name = x.get('name')

            if two is not None:
                by_2[two] = name
                codes2.add(two)
                m2to3[two] = threet
                m3to2[threeb] = m3to2[threet] = two
            by_3b[threeb] = name
            by_3t[threet] = name
            if threeb != threet:
                m3bto3t[threeb] = threet
            codes3b.add(threeb)
            codes3t.add(threet)
            base_name = name.lower()
            nm[base_name] = threet

        x = {'by_2':by_2, 'by_3b':by_3b, 'by_3t':by_3t, 'codes2':codes2,
                'codes3b':codes3b, 'codes3t':codes3t, '2to3':m2to3,
                '3to2':m3to2, '3bto3t':m3bto3t, 'name_map':nm}
        cPickle.dump(x, open(dest, 'wb'), -1)

    def clean(self):
        if os.path.exists(self.DEST):
            os.remove(self.DEST)

# }}}


class ISO3166(ISO639):  # {{{

    description = 'Compile country code maps for performance'
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'iso3166.pickle')

    def run(self, opts):
        src = self.j(self.d(self.SRC), 'setup', 'iso3166.xml')
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        dest = self.DEST
        base = self.d(dest)
        if not os.path.exists(base):
            os.makedirs(base)
        if not self.newer(dest, [src, __file__]):
            self.info('Pickled code is up to date')
            return
        self.info('Pickling ISO-3166 codes to', dest)
        from lxml import etree
        root = etree.fromstring(open(src, 'rb').read())
        codes = set()
        three_map = {}
        name_map = {}
        for x in root.xpath('//iso_3166_entry'):
            two = x.get('alpha_2_code')
            three = x.get('alpha_3_code')
            codes.add(two)
            name_map[two] = x.get('name')
            if three:
                three_map[three] = two
        x = {'names':name_map, 'codes':frozenset(codes), 'three_map':three_map}
        cPickle.dump(x, open(dest, 'wb'), -1)
# }}}
