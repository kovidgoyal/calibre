#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, tempfile, shutil, subprocess, glob, re, time, textwrap
from functools import partial

from setup import Command, __appname__, __version__, require_git_master

def qt_sources():
    qtdir = glob.glob('/usr/src/qt-*')[-1]
    j = partial(os.path.join, qtdir)
    return list(map(j, [
            'src/gui/widgets/qdialogbuttonbox.cpp',
    ]))

class POT(Command):  # {{{

    description = 'Update the .pot translation template and upload it'
    LP_BASE = os.path.join(os.path.dirname(os.path.dirname(Command.SRC)), 'calibre-translations')
    LP_SRC = os.path.join(LP_BASE, 'src')
    LP_PATH = os.path.join(LP_SRC, os.path.join(__appname__, 'translations'))
    LP_ISO_PATH = os.path.join(LP_BASE, 'setup', 'iso_639')

    def upload_pot(self, pot):
        msg = 'Updated translations template'
        subprocess.check_call(['bzr', 'commit', '-m', msg, pot])

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

    def run(self, opts):
        require_git_master()
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
                '--no-wrap', '-kQT_TRANSLATE_NOOP:2',
                ] + qt_inputs)

            with open(out.name, 'rb') as f:
                src = f.read()
            os.remove(out.name)
            src = pot_header + '\n' + src
            src += '\n\n' + self.get_tweaks_docs()
            pot = os.path.join(self.LP_PATH, __appname__+'.pot')
            with open(pot, 'wb') as f:
                f.write(src)
            self.info('Translations template:', os.path.abspath(pot))
            self.upload_pot(os.path.abspath(pot))

        return pot
# }}}

class Translations(POT):  # {{{
    description='''Compile the translations'''
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'locales')

    def po_files(self):
        return glob.glob(os.path.join(self.LP_PATH, '*.po'))

    def mo_file(self, po_file):
        locale = os.path.splitext(os.path.basename(po_file))[0]
        return locale, os.path.join(self.DEST, locale, 'messages.mo')

    def run(self, opts):
        self.iso639_errors = []
        for f in self.po_files():
            locale, dest = self.mo_file(f)
            base = os.path.dirname(dest)
            if not os.path.exists(base):
                os.makedirs(base)
            self.info('\tCompiling translations for', locale)
            subprocess.check_call(['msgfmt', '-o', dest, f])
            iscpo = {'bn':'bn_IN', 'zh_HK':'zh_CN'}.get(locale, locale)
            iso639 = self.j(self.LP_ISO_PATH, '%s.po'%iscpo)

            if os.path.exists(iso639):
                self.check_iso639(iso639)
                dest = self.j(self.d(dest), 'iso639.mo')
                if self.newer(dest, iso639):
                    self.info('\tCopying ISO 639 translations for %s' % iscpo)
                    subprocess.check_call(['msgfmt', '-o', dest, iso639])
            elif locale not in ('en_GB', 'en_CA', 'en_AU', 'si', 'ur', 'sc',
                    'ltg', 'nds', 'te', 'yi', 'fo', 'sq', 'ast', 'ml', 'ku',
                    'fr_CA', 'him', 'jv', 'ka', 'fur', 'ber'):
                self.warn('No ISO 639 translations for locale:', locale)

        if self.iso639_errors:
            for err in self.iso639_errors:
                print (err)
            raise SystemExit(1)

        self.write_stats()
        self.freeze_locales()

    def check_iso639(self, path):
        from calibre.utils.localization import langnames_to_langcodes
        with open(path, 'rb') as f:
            raw = f.read()
        rmap = {}
        msgid = None
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
                        self.iso639_errors.append('In file %s the name %s is used as translation for both %s and %s' % (
                            os.path.basename(path), msgstr, msgid, rmap[msgstr]))
                    # raise SystemExit(1)
                rmap[msgstr] = msgid

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
        raw = self.get_stats(self.j(self.LP_PATH, 'calibre.pot'))
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
        zf = self.DEST + '.zip'
        if os.path.exists(zf):
            os.remove(zf)

# }}}

class GetTranslations(Translations):  # {{{

    description = 'Get updated translations from Launchpad'
    BRANCH = 'lp:~kovid/calibre/translations'
    LP_BASE = os.path.dirname(POT.LP_SRC)
    CMSG = 'Updated translations'

    @property
    def modified_translations(self):
        raw = subprocess.check_output(['bzr', 'status', '-S', self.LP_PATH]).strip()
        ans = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith('M') and line.endswith('.po'):
                ans.append(line.split()[-1])
        return ans

    def resolve_conflicts(self):
        conflict = False
        for line in subprocess.check_output(['bzr', 'status'], cwd=self.LP_BASE).splitlines():
            if line == 'conflicts:':
                conflict = True
                break
        if not conflict:
            raise Exception('bzr merge failed and no conflicts found')
        subprocess.check_call(['bzr', 'resolve', '--take-other'], cwd=self.LP_BASE)

    def run(self, opts):
        require_git_master()
        if not self.modified_translations:
            try:
                subprocess.check_call(['bzr', 'merge', self.BRANCH], cwd=self.LP_BASE)
            except subprocess.CalledProcessError:
                self.resolve_conflicts()
        self.check_for_errors()

        if self.modified_translations:
            subprocess.check_call(['bzr', 'commit', '-m',
                self.CMSG], cwd=self.LP_BASE)
        else:
            print('No updated translations available')

    def check_for_errors(self):
        errors = os.path.join(tempfile.gettempdir(), 'calibre-translation-errors')
        if os.path.exists(errors):
            shutil.rmtree(errors)
        os.mkdir(errors)
        pofilter = ('pofilter', '-i', self.LP_PATH, '-o', errors,
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
        if errfiles:
            subprocess.check_call(['gvim', '-f', '-p', '--']+errfiles)
            for f in errfiles:
                with open(f, 'r+b') as f:
                    raw = f.read()
                    raw = re.sub(r'# \(pofilter\).*', '', raw)
                    f.seek(0)
                    f.truncate()
                    f.write(raw)

            subprocess.check_call(['pomerge', '-t', self.LP_PATH, '-i', errors, '-o',
                self.LP_PATH])
            return True
        return False

# }}}

class ISO639(Command):  # {{{

    description = 'Compile translations for ISO 639 codes'
    DEST = os.path.join(os.path.dirname(POT.SRC), 'resources', 'localization',
            'iso639.pickle')

    def run(self, opts):
        src = POT.LP_ISO_PATH
        if not os.path.exists(src):
            raise Exception(src + ' does not exist')
        dest = self.DEST
        if not self.newer(dest, [src, __file__]):
            self.info('Pickled code is up to date')
            return
        self.info('Pickling ISO-639 codes to', dest)
        from lxml import etree
        root = etree.fromstring(open(self.j(src, 'iso_639_3.xml'), 'rb').read())
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
                # Only recognize langauges in ISO-639-2
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

        from cPickle import dump
        x = {'by_2':by_2, 'by_3b':by_3b, 'by_3t':by_3t, 'codes2':codes2,
                'codes3b':codes3b, 'codes3t':codes3t, '2to3':m2to3,
                '3to2':m3to2, '3bto3t':m3bto3t, 'name_map':nm}
        dump(x, open(dest, 'wb'), -1)

    def clean(self):
        if os.path.exists(self.DEST):
            os.remove(self.DEST)

# }}}

