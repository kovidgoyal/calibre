#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil, subprocess, glob, re, time, textwrap
from distutils import sysconfig
from functools import partial

from setup import Command, __appname__, __version__

def qt_sources():
    qtdir = glob.glob('/usr/src/qt-*')[-1]
    j = partial(os.path.join, qtdir)
    return list(map(j, [
            'src/gui/widgets/qdialogbuttonbox.cpp',
    ]))

class POT(Command): # {{{

    description = 'Update the .pot translation template'
    PATH = os.path.join(Command.SRC, __appname__, 'translations')

    def source_files(self):
        ans = []
        for root, _, files in os.walk(os.path.dirname(self.PATH)):
            for name in files:
                if name.endswith('.py'):
                    ans.append(os.path.abspath(os.path.join(root, name)))
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


    def run(self, opts):
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
                '--no-wrap', '-k__',
                ])
            subprocess.check_call(['xgettext', '-j',
                '--default-domain=calibre', '-o', out.name,
                '--from-code=UTF-8', '--sort-by-file', '--omit-header',
                '--no-wrap', '-kQT_TRANSLATE_NOOP:2',
                ] + qt_inputs)

            with open(out.name, 'rb') as f:
                src = f.read()
            os.remove(out.name)
            src = pot_header + '\n' + src
            src += '\n\n' + self.get_tweaks_docs()
            pot = os.path.join(self.PATH, __appname__+'.pot')
            with open(pot, 'wb') as f:
                f.write(src)
            self.info('Translations template:', os.path.abspath(pot))


        return pot
# }}}

class Translations(POT):
    description='''Compile the translations'''
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'locales')

    def po_files(self):
        return glob.glob(os.path.join(self.PATH, '*.po'))

    def mo_file(self, po_file):
        locale = os.path.splitext(os.path.basename(po_file))[0]
        return locale, os.path.join(self.DEST, locale, 'messages.mo')

    def run(self, opts):
        for f in self.po_files():
            locale, dest = self.mo_file(f)
            base = os.path.dirname(dest)
            if not os.path.exists(base):
                os.makedirs(base)
            self.info('\tCompiling translations for', locale)
            subprocess.check_call(['msgfmt', '-o', dest, f])
            if locale in ('en_GB', 'en_CA', 'en_AU', 'si', 'ur', 'sc', 'ltg', 'nds', 'te', 'yi'):
                continue
            pycountry = self.j(sysconfig.get_python_lib(), 'pycountry',
                    'locales', locale, 'LC_MESSAGES')
            if os.path.exists(pycountry):
                iso639 = self.j(pycountry, 'iso639.mo')
                dest = self.j(self.d(dest), self.b(iso639))
                if self.newer(dest, iso639) and os.path.exists(iso639):
                    self.info('\tCopying ISO 639 translations')
                    shutil.copy2(iso639, dest)
            else:
                self.warn('No ISO 639 translations for locale:', locale,
                '\nDo you have pycountry installed?')

        self.write_stats()
        self.freeze_locales()

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

    def get_stats(self, path):
        return subprocess.Popen(['msgfmt', '--statistics', '-o', '/dev/null',
            path],
            stderr=subprocess.PIPE).stderr.read()

    def write_stats(self):
        files = self.po_files()
        dest = self.stats
        if not self.newer(dest, files):
            return
        self.info('Calculating translation statistics...')
        raw = self.get_stats(self.j(self.PATH, 'calibre.pot'))
        total = int(raw.split(',')[-1].strip().split()[0])
        stats = {}
        for f in files:
            raw = self.get_stats(f)
            trans = int(raw.split()[0])
            locale = self.mo_file(f)[0]
            stats[locale] = min(1.0, float(trans)/total)


        import cPickle
        cPickle.dump(stats, open(dest, 'wb'), -1)

    def clean(self):
        if os.path.exists(self.stats):
            os.remove(self.stats)
        for f in self.po_files():
            l, d = self.mo_file(f)
            i = self.j(self.d(d), 'iso639.mo')
            j = self.j(self.d(d), 'qt.qm')
            for x in (i, j, d):
                if os.path.exists(x):
                    os.remove(x)


class GetTranslations(Translations):

    description = 'Get updated translations from Launchpad'
    BRANCH = 'lp:~kovid/calibre/translations'

    @classmethod
    def modified_translations(cls):
        raw = subprocess.Popen(['bzr', 'status'],
                stdout=subprocess.PIPE).stdout.read().strip()
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith(cls.PATH) and line.endswith('.po'):
                yield line

    def run(self, opts):
        if len(list(self.modified_translations())) == 0:
            subprocess.check_call(['bzr', 'merge', self.BRANCH])
        if len(list(self.modified_translations())) == 0:
            print 'No updated translations available'
        else:
            subprocess.check_call(['bzr', 'commit', '-m',
                'IGN:Updated translations', self.PATH])
        self.check_for_errors()

    @classmethod
    def check_for_errors(cls):
        errors = os.path.join(tempfile.gettempdir(), 'calibre-translation-errors')
        if os.path.exists(errors):
            shutil.rmtree(errors)
        os.mkdir(errors)
        pofilter = ('pofilter', '-i', cls.PATH, '-o', errors,
                '-t', 'accelerators', '-t', 'escapes', '-t', 'variables',
                #'-t', 'xmltags',
                #'-t', 'brackets',
                #'-t', 'emails',
                #'-t', 'doublequoting',
                #'-t', 'filepaths',
                #'-t', 'numbers',
                '-t', 'options',
                #'-t', 'urls',
                '-t', 'printf')
        subprocess.check_call(pofilter)
        errfiles = glob.glob(errors+os.sep+'*.po')
        subprocess.check_call(['gvim', '-f', '-p', '--']+errfiles)
        for f in errfiles:
            with open(f, 'r+b') as f:
                raw = f.read()
                raw = re.sub(r'# \(pofilter\).*', '', raw)
                f.seek(0)
                f.truncate()
                f.write(raw)

        subprocess.check_call(['pomerge', '-t', cls.PATH, '-i', errors, '-o',
            cls.PATH])
        if len(list(cls.modified_translations())) > 0:
            subprocess.call(['bzr', 'diff', cls.PATH])
            yes = raw_input('Merge corrections? [y/n]: ').strip()
            if yes in ['', 'y']:
                subprocess.check_call(['bzr', 'commit', '-m',
                    'IGN:Translation corrections', cls.PATH])


class ISO639(Command):

    description = 'Compile translations for ISO 639 codes'
    XML = '/usr/lib/python2.7/site-packages/pycountry/databases/iso639.xml'

    def run(self, opts):
        src = self.XML
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        dest = self.j(self.d(self.SRC), 'resources', 'localization',
                'iso639.pickle')
        if not self.newer(dest, src):
            self.info('Pickled code is up to date')
            return
        self.info('Pickling ISO-639 codes to', dest)
        from lxml import etree
        root = etree.fromstring(open(src, 'rb').read())
        by_2 = {}
        by_3b = {}
        by_3t = {}
        codes2, codes3t, codes3b = set([]), set([]), set([])
        for x in root.xpath('//iso_639_entry'):
            name = x.get('name')
            two = x.get('iso_639_1_code', None)
            if two is not None:
                by_2[two] = name
                codes2.add(two)
            by_3b[x.get('iso_639_2B_code')] = name
            by_3t[x.get('iso_639_2T_code')] = name
            codes3b.add(x.get('iso_639_2B_code'))
            codes3t.add(x.get('iso_639_2T_code'))

        from cPickle import dump
        x = {'by_2':by_2, 'by_3b':by_3b, 'by_3t':by_3t, 'codes2':codes2,
                'codes3b':codes3b, 'codes3t':codes3t}
        dump(x, open(dest, 'wb'), -1)

