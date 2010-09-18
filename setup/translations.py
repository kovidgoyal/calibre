#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cStringIO, tempfile, shutil, atexit, subprocess, glob, re
from distutils import sysconfig

from setup import Command, __appname__
from setup.pygettext import main as pygettext
from setup.build_environment import pyqt

class POT(Command):

    description = 'Update the .pot translation template'
    PATH = os.path.join(Command.SRC, __appname__, 'translations')

    def source_files(self):
        ans = []
        for root, _, files in os.walk(os.path.dirname(self.PATH)):
            for name in files:
                if name.endswith('.py'):
                    ans.append(os.path.abspath(os.path.join(root, name)))
        return ans


    def run(self, opts):
        files = self.source_files()
        buf = cStringIO.StringIO()
        self.info('Creating translations template...')
        tempdir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, tempdir)
        pygettext(buf, ['-k', '__', '-p', tempdir]+files)
        src = buf.getvalue()
        pot = os.path.join(self.PATH, __appname__+'.pot')
        f = open(pot, 'wb')
        f.write(src)
        f.close()
        self.info('Translations template:', os.path.abspath(pot))
        return pot


class Translations(POT):
    description='''Compile the translations'''
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'locales')

    def po_files(self):
        return glob.glob(os.path.join(self.PATH, '*.po'))

    def mo_file(self, po_file):
        locale = os.path.splitext(os.path.basename(po_file))[0]
        return locale, os.path.join(self.DEST, locale, 'LC_MESSAGES', 'messages.mo')


    def run(self, opts):
        for f in self.po_files():
            locale, dest = self.mo_file(f)
            base = os.path.dirname(dest)
            if not os.path.exists(base):
                os.makedirs(base)
            if self.newer(dest, f):
                self.info('\tCompiling translations for', locale)
                subprocess.check_call(['msgfmt', '-o', dest, f])
            if locale in ('en_GB', 'nds', 'te', 'yi'):
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

        base = os.path.join(pyqt.qt_data_dir, 'translations')
        qt_translations = glob.glob(os.path.join(base, 'qt_*.qm'))
        if not qt_translations:
            raise Exception('Could not find qt translations')
        for f in qt_translations:
            locale = self.s(self.b(f))[0][3:]
            dest = self.j(self.DEST, locale, 'LC_MESSAGES', 'qt.qm')
            if self.e(self.d(dest)) and self.newer(dest, f):
                self.info('\tCopying Qt translation for locale:', locale)
                shutil.copy2(f, dest)

        self.write_stats()

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

