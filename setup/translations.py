#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil, subprocess, glob, re, time, textwrap, cPickle, shlex, json, errno
from locale import normalize as normalize_locale
from functools import partial

from setup import Command, __appname__, __version__, require_git_master
from setup.parallel_build import parallel_check_output

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
        return subprocess.check_call(['tx'] + cmd, **kw)

    def git(self, cmd, **kw):
        kw['cwd'] = kw.get('cwd', self.TRANSLATIONS)
        if hasattr(cmd, 'format'):
            cmd = shlex.split(cmd)
        f = getattr(subprocess, ('call' if kw.pop('use_call', False) else 'check_call'))
        return f(['git'] + cmd, **kw)

    def upload_pot(self, pot, resource='main'):
        self.tx(['push', '-r', 'calibre.'+resource, '-s'], cwd=self.TRANSLATIONS)

    def source_files(self):
        ans = []
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
            self.upload_pot(dest, resource=slug)
            self.git(['add', dest])
        shutil.rmtree(base)

    def run(self, opts):
        require_git_master()
        self.get_user_manual_docs()
        pot_header = textwrap.dedent('''\
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

        ''')%dict(appname=__appname__, version=__version__,
                year=time.strftime('%Y'),
                time=time.strftime('%Y-%m-%d %H:%M+%Z'))

        files = self.source_files()
        qt_inputs = qt_sources()

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
            self.upload_pot(os.path.abspath(pot))

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

    def po_files(self):
        return glob.glob(os.path.join(self.TRANSLATIONS, __appname__, '*.po'))

    def mo_file(self, po_file):
        locale = os.path.splitext(os.path.basename(po_file))[0]
        return locale, os.path.join(self.DEST, locale, 'messages.mo')

    def run(self, opts):
        l = {}
        exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lc_data.py'))
             .read(), os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lc_data.py'), 'exec'), l, l)
        lcdata = {k:{k1:v1 for k1, v1 in v} for k, v in l['data']}
        self.iso639_errors = []
        jobs = []
        for f in self.po_files():
            locale, dest = self.mo_file(f)
            base = os.path.dirname(dest)
            if not os.path.exists(base):
                os.makedirs(base)
            jobs.append(['msgfmt', '-o', dest, f])
            iscpo = {'bn':'bn_IN', 'zh_HK':'zh_CN'}.get(locale, locale)
            iso639 = self.j(self.TRANSLATIONS, 'iso_639', '%s.po'%iscpo)

            if os.path.exists(iso639) and self.check_iso639(iso639):
                dest = self.j(self.d(dest), 'iso639.mo')
                if self.newer(dest, iso639):
                    jobs.append(['msgfmt', '-o', dest, iso639])
            elif locale not in {
                'en_GB', 'en_CA', 'en_AU', 'si', 'ur', 'sc', 'ltg', 'nds',
                'te', 'yi', 'fo', 'sq', 'ast', 'ml', 'ku', 'fr_CA', 'him',
                'jv', 'ka', 'fur', 'ber', 'my', 'fil', 'hy', 'ug'}:
                self.warn('No ISO 639 translations for locale:', locale)

            ln = normalize_locale(locale).partition('.')[0]
            if ln in lcdata:
                ld = lcdata[ln]
                lcdest = self.j(self.d(dest), 'lcdata.pickle')
                with open(lcdest, 'wb') as lcf:
                    lcf.write(cPickle.dumps(ld, -1))
        self.info('\nCompiling %d translation files...' % len(jobs))
        tuple(parallel_check_output(jobs, self.info))

        if self.iso639_errors:
            for err in self.iso639_errors:
                print (err)
            raise SystemExit(1)

        self.write_stats()
        self.freeze_locales()
        self.compile_user_manual_translations()

    def check_iso639(self, path):
        from calibre.utils.localization import langnames_to_langcodes
        with open(path, 'rb') as f:
            raw = f.read()
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

    def write_stats(self):
        files = self.po_files()
        dest = self.stats
        if not self.newer(dest, files):
            return
        self.info('Calculating translation statistics...')
        stats = {}
        jobs = (
            ['msgfmt', '--statistics', '-o', os.devnull, x] for x in files
        )
        for f, line in zip(files, parallel_check_output(jobs, self.info)):
            nums = tuple(map(int, re.findall(r'\d+', line)))
            trans = nums[0]
            total = trans if len(nums) == 1 else (trans + nums[1])
            locale = self.mo_file(f)[0]
            stats[locale] = min(1.0, float(trans)/total)

        base = self.d(dest)
        try:
            os.mkdir(base)
        except EnvironmentError as err:
            if err.errno != errno.EEXIST:
                raise
        cPickle.dump(stats, open(dest, 'wb'), -1)

    def compile_user_manual_translations(self):
        self.info('Compiling user manual translations...')
        srcbase = self.j(self.d(self.SRC), 'translations', 'manual')
        destbase = self.j(self.d(self.SRC), 'manual', 'locale')
        complete = {}
        for x in os.listdir(srcbase):
            q = self.j(srcbase, x)
            if not os.path.isdir(q):
                continue
            dest = self.j(destbase, x, 'LC_MESSAGES')
            if os.path.exists(dest):
                shutil.rmtree(dest)
            os.makedirs(dest)
            jobs = []
            for po in os.listdir(q):
                if not po.endswith('.po'):
                    continue
                jobs.append([
                    'msgfmt', '--statistics', '-o', self.j(
                        dest, po.rpartition('.')[0] + '.mo'), self.j(q, po)])
            stats = tuple(parallel_check_output(jobs, self.info))
            translated = untranslated = 0
            for line in stats:
                nums = tuple(map(int, re.findall(r'\d+', line)))
                translated += nums[0]
                if len(nums) > 1:
                    untranslated += nums[1]
            stats = {'translated':translated, 'untranslated':untranslated}
            with open(self.j(self.d(dest), 'stats.json'), 'wb') as f:
                json.dump(stats, f)
            total = translated + untranslated
            # Raise the 30% threshold in the future
            if total and (translated / float(total)) > 0.3:
                complete[x] = stats
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

# }}}

class GetTranslations(Translations):  # {{{

    description = 'Get updated translations from Transifex'

    @property
    def is_modified(self):
        return bool(subprocess.check_output('git status --porcelain'.split(), cwd=self.TRANSLATIONS))

    def run(self, opts):
        require_git_master()
        self.tx('pull -a')
        if self.is_modified:
            self.check_for_errors()
            self.upload_to_vcs()
        else:
            print ('No translations were updated')

    def check_for_errors(self):
        errors = os.path.join(tempfile.gettempdir(), 'calibre-translation-errors')
        if os.path.exists(errors):
            shutil.rmtree(errors)
        os.mkdir(errors)
        tpath = self.j(self.TRANSLATIONS, __appname__)
        pofilter = ('pofilter', '-i', tpath, '-o', errors,
                '-t', 'accelerators', '-t', 'escapes', '-t', 'variables',
                # '-t', 'xmltags',
                # '-t', 'brackets',
                # '-t', 'emails',
                # '-t', 'doublequoting',
                # '-t', 'filepaths',
                # '-t', 'numbers',
                '-t', 'options',
                # '-t', 'urls',
                '-t', 'printf')
        subprocess.check_call(pofilter)
        errfiles = glob.glob(errors+os.sep+'*.po')
        if errfiles:
            subprocess.check_call(['gvim', '-f', '-p', '--']+errfiles)
            for f in errfiles:
                with open(f, 'r+b') as f:
                    raw = f.read()
                    raw = re.sub(r'# \(pofilter\).*', '', raw)
                    f.seek(0)
                    f.truncate()
                    f.write(raw)

            subprocess.check_call(['pomerge', '-t', tpath, '-i', errors, '-o', tpath])
            languages = []
            for f in glob.glob(self.j(errors, '*.po')):
                lc = os.path.basename(f).rpartition('.')[0]
                languages.append(lc)
            if languages:
                print('Pushing fixes for languages: %s' % (', '.join(languages)))
                self.tx('push -r calibre.main -t -l ' + ','.join(languages))
            return True
        return False

    def upload_to_vcs(self):
        print ('Uploading updated translations to version control')
        cc = partial(subprocess.check_call, cwd=self.TRANSLATIONS)
        cc('git add */*.po'.split())
        cc('git commit -am'.split() + ['Updated translations'])
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
