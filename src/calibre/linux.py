__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

''' Post installation script for linux '''

import sys, os, cPickle, textwrap, stat, importlib
from subprocess import check_call

from calibre import  __appname__, prints, guess_type
from calibre.constants import islinux, isnetbsd, isbsd
from calibre.customize.ui import all_input_formats
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir


entry_points = {
        'console_scripts': [ \
             'ebook-device       = calibre.devices.prs500.cli.main:main',
             'ebook-meta         = calibre.ebooks.metadata.cli:main',
             'ebook-convert      = calibre.ebooks.conversion.cli:main',
             'markdown-calibre   = calibre.ebooks.markdown.markdown:main',
             'web2disk           = calibre.web.fetch.simple:main',
             'calibre-server     = calibre.library.server.main:main',
             'lrf2lrs            = calibre.ebooks.lrf.lrfparser:main',
             'lrs2lrf            = calibre.ebooks.lrf.lrs.convert_from:main',
             'calibre-debug      = calibre.debug:main',
             'calibredb          = calibre.library.cli:main',
             'calibre-parallel   = calibre.utils.ipc.worker:main',
             'calibre-customize  = calibre.customize.ui:main',
             'calibre-complete   = calibre.utils.complete:main',
             'pdfmanipulate      = calibre.ebooks.pdf.manipulate.cli:main',
             'fetch-ebook-metadata = calibre.ebooks.metadata.sources.cli:main',
             'epub-fix           = calibre.ebooks.epub.fix.main:main',
             'calibre-smtp = calibre.utils.smtp:main',
        ],
        'gui_scripts'    : [
            __appname__+' = calibre.gui2.main:main',
            'lrfviewer    = calibre.gui2.lrf_renderer.main:main',
            'ebook-viewer = calibre.gui2.viewer.main:main',
                            ],
      }

class PreserveMIMEDefaults(object):

    def __init__(self):
        self.initial_values = {}

    def __enter__(self):
        def_data_dirs = '/usr/local/share:/usr/share'
        paths = os.environ.get('XDG_DATA_DIRS', def_data_dirs)
        paths = paths.split(':')
        paths.append(os.environ.get('XDG_DATA_HOME', os.path.expanduser(
            '~/.local/share')))
        paths = list(filter(os.path.isdir, paths))
        if not paths:
            # Env var had garbage in it, ignore it
            paths = def_data_dirs.split(':')
        paths = list(filter(os.path.isdir, paths))
        self.paths = {os.path.join(x, 'applications/defaults.list') for x in
                paths}
        self.initial_values = {}
        for x in self.paths:
            try:
                with open(x, 'rb') as f:
                    self.initial_values[x] = f.read()
            except:
                self.initial_values[x] = None

    def __exit__(self, *args):
        for path, val in self.initial_values.iteritems():
            if val is None:
                try:
                    os.remove(path)
                except:
                    pass
            elif os.path.exists(path):
                with open(path, 'r+b') as f:
                    if f.read() != val:
                        f.seek(0)
                        f.truncate()
                        f.write(val)

# Uninstall script {{{
UNINSTALL = '''\
#!{python}
euid = {euid}

import os, subprocess, shutil

if os.geteuid() != euid:
    print 'WARNING: uninstaller must be run as', euid, 'to remove all files'

for x in {manifest!r}:
    if not os.path.exists(x): continue
    print 'Removing', x
    try:
        if os.path.isdir(x):
            shutil.rmtree(x)
        else:
            os.unlink(x)
    except Exception as e:
        print 'Failed to delete', x
        print '\t', e

icr = {icon_resources!r}
for context, name, size in icr:
    cmd = ['xdg-icon-resource', 'uninstall', '--context', context, '--size', size, name]
    if (context, name) != icr[-1]:
        cmd.insert(2, '--noupdate')
    ret = subprocess.call(cmd)
    if ret != 0:
        print 'WARNING: Failed to remove icon', name

mr = {menu_resources!r}
for f in mr:
    cmd = ['xdg-desktop-menu', 'uninstall', f]
    ret = subprocess.call(cmd)
    if ret != 0:
        print 'WARNING: Failed to remove menu item', f

os.remove(os.path.abspath(__file__))
'''

# }}}

class PostInstall:

    def task_failed(self, msg):
        self.warn(msg, 'with error:')
        import traceback
        tb = '\n\t'.join(traceback.format_exc().splitlines())
        self.info('\t'+tb)
        print

    def warning(self, *args, **kwargs):
        print '\n'+'_'*20, 'WARNING','_'*20
        prints(*args, **kwargs)
        print '_'*50
        self.warnings.append((args, kwargs))
        sys.stdout.flush()


    def __init__(self, opts, info=prints, warn=None, manifest=None):
        self.opts = opts
        self.info = info
        self.warn = warn
        self.warnings = []
        if self.warn is None:
            self.warn = self.warning

        if not self.opts.staging_bindir:
            self.opts.staging_bindir = os.path.join(self.opts.staging_root,
            'bin')
        if not self.opts.staging_sharedir:
            self.opts.staging_sharedir = os.path.join(self.opts.staging_root,
            'share', 'calibre')
        self.opts.staging_etc = '/etc' if self.opts.staging_root == '/usr' else \
                os.path.join(self.opts.staging_root, 'etc')

        scripts = cPickle.loads(P('scripts.pickle', data=True))
        if getattr(sys, 'frozen_path', False):
            self.info('Creating symlinks...')
            for exe in scripts.keys():
                dest = os.path.join(self.opts.staging_bindir, exe)
                if os.path.lexists(dest):
                    os.unlink(dest)
                tgt = os.path.join(getattr(sys, 'frozen_path'), exe)
                self.info('\tSymlinking %s to %s'%(tgt, dest))
                os.symlink(tgt, dest)

        if manifest is None:
            manifest = [os.path.abspath(os.path.join(opts.staging_bindir, x)) for x in
                scripts.keys()]
        self.manifest = manifest
        self.icon_resources = []
        self.menu_resources = []
        self.mime_resources = []
        if islinux or isbsd:
            self.setup_completion()
        self.install_man_pages()
        if islinux or isbsd:
            self.setup_desktop_integration()
        self.create_uninstaller()

        from calibre.utils.config import config_dir
        if os.path.exists(config_dir):
            os.chdir(config_dir)
            if islinux or isbsd:
                for f in os.listdir('.'):
                    if os.stat(f).st_uid == 0:
                        import shutil
                        shutil.rmtree(f) if os.path.isdir(f) else os.unlink(f)
                if os.stat(config_dir).st_uid == 0:
                    os.rmdir(config_dir)

        if warn is None and self.warnings:
            self.info('There were %d warnings'%len(self.warnings))
            for args, kwargs in self.warnings:
                self.info('*', *args, **kwargs)
                print

    def create_uninstaller(self):
        dest = os.path.join(self.opts.staging_bindir, 'calibre-uninstall')
        raw = UNINSTALL.format(python=os.path.abspath(sys.executable), euid=os.geteuid(),
                manifest=self.manifest, icon_resources=self.icon_resources,
                menu_resources=self.menu_resources)
        try:
            with open(dest, 'wb') as f:
                f.write(raw)
            os.chmod(dest, stat.S_IRWXU|stat.S_IRGRP|stat.S_IROTH)
            if os.geteuid() == 0:
                os.chown(dest, 0, 0)
        except:
            if self.opts.fatal_errors:
                raise
            self.task_failed('Creating uninstaller failed')


    def setup_completion(self): # {{{
        try:
            self.info('Setting up bash completion...')
            from calibre.ebooks.metadata.cli import option_parser as metaop, filetypes as meta_filetypes
            from calibre.ebooks.lrf.lrfparser import option_parser as lrf2lrsop
            from calibre.gui2.lrf_renderer.main import option_parser as lrfviewerop
            from calibre.gui2.viewer.main import option_parser as viewer_op
            from calibre.ebooks.metadata.sources.cli import option_parser as fem_op
            from calibre.gui2.main import option_parser as guiop
            from calibre.utils.smtp import option_parser as smtp_op
            from calibre.library.server.main import option_parser as serv_op
            from calibre.ebooks.epub.fix.main import option_parser as fix_op
            from calibre.ebooks import BOOK_EXTENSIONS
            input_formats = sorted(all_input_formats())
            bc = os.path.join(os.path.dirname(self.opts.staging_sharedir),
                'bash-completion')
            if os.path.exists(bc):
                f = os.path.join(bc, 'calibre')
            else:
                if isnetbsd:
                    f = os.path.join(self.opts.staging_root, 'share/bash_completion.d/calibre')
                else:
                    f = os.path.join(self.opts.staging_etc, 'bash_completion.d/calibre')
            if not os.path.exists(os.path.dirname(f)):
                os.makedirs(os.path.dirname(f))
            self.manifest.append(f)
            complete = 'calibre-complete'
            if getattr(sys, 'frozen_path', None):
                complete = os.path.join(getattr(sys, 'frozen_path'), complete)

            self.info('Installing bash completion to', f)
            with open(f, 'wb') as f:
                f.write('# calibre Bash Shell Completion\n')
                f.write(opts_and_exts('calibre', guiop, BOOK_EXTENSIONS))
                f.write(opts_and_exts('lrf2lrs', lrf2lrsop, ['lrf']))
                f.write(opts_and_exts('ebook-meta', metaop, list(meta_filetypes())))
                f.write(opts_and_exts('lrfviewer', lrfviewerop, ['lrf']))
                f.write(opts_and_exts('ebook-viewer', viewer_op, input_formats))
                f.write(opts_and_words('fetch-ebook-metadata', fem_op, []))
                f.write(opts_and_words('calibre-smtp', smtp_op, []))
                f.write(opts_and_words('calibre-server', serv_op, []))
                f.write(opts_and_exts('epub-fix', fix_op, ['epub']))
                f.write(textwrap.dedent('''
                _ebook_device_ls()
                {
                local pattern search listing prefix
                pattern="$1"
                search="$1"
                if [[ -n "{$pattern}" ]]; then
                    if [[ "${pattern:(-1)}" == "/" ]]; then
                    pattern=""
                    else
                    pattern="$(basename ${pattern} 2> /dev/null)"
                    search="$(dirname ${search} 2> /dev/null)"
                    fi
                fi

                if [[  "x${search}" == "x" || "x${search}" == "x." ]]; then
                    search="/"
                fi

                listing="$(ebook-device ls ${search} 2>/dev/null)"

                prefix="${search}"
                if [[ "x${prefix:(-1)}" != "x/" ]]; then
                    prefix="${prefix}/"
                fi

                echo $(compgen -P "${prefix}" -W "${listing}" "${pattern}")
                }

                _ebook_device()
                {
                local cur prev
                cur="${COMP_WORDS[COMP_CWORD]}"
                prev="${COMP_WORDS[COMP_CWORD-1]}"
                COMPREPLY=()
                case "${prev}" in
                    ls|rm|mkdir|touch|cat )
                        COMPREPLY=( $(_ebook_device_ls "${cur}") )
                        return 0
                        ;;
                    cp )
                        if [[ ${cur} == prs500:* ]]; then
                        COMPREPLY=( $(_ebook_device_ls "${cur:7}") )
                        return 0
                        else
                        _filedir
                        return 0
                        fi
                        ;;
                    prs500 )
                        COMPREPLY=( $(compgen -W "cp ls rm mkdir touch cat info books df" "${cur}") )
                        return 0
                        ;;
                    * )
                        if [[ ${cur} == prs500:* ]]; then
                        COMPREPLY=( $(_ebook_device_ls "${cur:7}") )
                        return 0
                        else
                        if [[ ${prev} == prs500:* ]]; then
                            _filedir
                            return 0
                        else
                            COMPREPLY=( $(compgen -W "prs500:" "${cur}") )
                            return 0
                        fi
                        return 0
                        fi
                    ;;
                esac
                }
                complete -o nospace  -F _ebook_device ebook-device

                complete -o nospace -C %s ebook-convert
                ''')%complete)
        except TypeError as err:
            if 'resolve_entities' in str(err):
                print 'You need python-lxml >= 2.0.5 for calibre'
                sys.exit(1)
            raise
        except:
            if self.opts.fatal_errors:
                raise
            self.task_failed('Setting up completion failed')
    # }}}

    def install_man_pages(self): # {{{
        try:
            from calibre.utils.help2man import create_man_page
            if isbsd:
                manpath = os.path.join(self.opts.staging_root, 'man/man1')
            else:
                manpath = os.path.join(self.opts.staging_sharedir, 'man/man1')
            if not os.path.exists(manpath):
                os.makedirs(manpath)
            self.info('Installing MAN pages...')
            for src in entry_points['console_scripts']:
                prog, right = src.split('=')
                prog = prog.strip()
                module = importlib.import_module(right.split(':')[0].strip())
                parser = getattr(module, 'option_parser', None)
                if parser is None:
                    continue
                parser = parser()
                raw = create_man_page(prog, parser)
                if isbsd:
                    manfile = os.path.join(manpath, prog+'.1')
                else:
                    manfile = os.path.join(manpath, prog+'.1'+__appname__+'.bz2')
                self.info('\tInstalling MAN page for', prog)
                open(manfile, 'wb').write(raw)
                self.manifest.append(manfile)
        except:
            if self.opts.fatal_errors:
                raise
            self.task_failed('Installing MAN pages failed')
    # }}}

    def setup_desktop_integration(self): # {{{
        try:
            self.info('Setting up desktop integration...')

            with TemporaryDirectory() as tdir, CurrentDir(tdir), \
                                PreserveMIMEDefaults():
                render_img('mimetypes/lrf.png', 'calibre-lrf.png')
                check_call('xdg-icon-resource install --noupdate --context mimetypes --size 128 calibre-lrf.png application-lrf', shell=True)
                self.icon_resources.append(('mimetypes', 'application-lrf', '128'))
                check_call('xdg-icon-resource install --noupdate --context mimetypes --size 128 calibre-lrf.png text-lrs', shell=True)
                self.icon_resources.append(('mimetypes', 'application-lrs',
                '128'))
                render_img('lt.png', 'calibre-gui.png')
                check_call('xdg-icon-resource install --noupdate --size 128 calibre-gui.png calibre-gui', shell=True)
                self.icon_resources.append(('apps', 'calibre-gui', '128'))
                render_img('viewer.png', 'calibre-viewer.png')
                check_call('xdg-icon-resource install --size 128 calibre-viewer.png calibre-viewer', shell=True)
                self.icon_resources.append(('apps', 'calibre-viewer', '128'))

                mimetypes = set([])
                for x in all_input_formats():
                    mt = guess_type('dummy.'+x)[0]
                    if mt and 'chemical' not in mt and 'ctc-posml' not in mt:
                        mimetypes.add(mt)

                def write_mimetypes(f):
                    f.write('MimeType=%s;\n'%';'.join(mimetypes))

                f = open('calibre-lrfviewer.desktop', 'wb')
                f.write(VIEWER)
                f.close()
                f = open('calibre-ebook-viewer.desktop', 'wb')
                f.write(EVIEWER)
                write_mimetypes(f)
                f.close()
                f = open('calibre-gui.desktop', 'wb')
                f.write(GUI)
                write_mimetypes(f)
                f.close()
                des = ('calibre-gui.desktop', 'calibre-lrfviewer.desktop',
                        'calibre-ebook-viewer.desktop')
                for x in des:
                    cmd = ['xdg-desktop-menu', 'install', '--noupdate', './'+x]
                    check_call(' '.join(cmd), shell=True)
                    self.menu_resources.append(x)
                check_call(['xdg-desktop-menu', 'forceupdate'])
                f = open('calibre-mimetypes', 'wb')
                f.write(MIME)
                f.close()
                self.mime_resources.append('calibre-mimetypes')
                check_call('xdg-mime install ./calibre-mimetypes', shell=True)
        except Exception:
            if self.opts.fatal_errors:
                raise
            self.task_failed('Setting up desktop integration failed')

    # }}}

def option_parser():
    from calibre.utils.config import OptionParser
    parser = OptionParser()
    parser.add_option('--make-errors-fatal', action='store_true', default=False,
                      dest='fatal_errors', help='If set die on errors.')
    parser.add_option('--root', dest='staging_root', default='/usr',
            help='Prefix under which to install files')
    parser.add_option('--bindir', default=None, dest='staging_bindir',
        help='Location where calibre launcher scripts were installed. Typically /usr/bin')
    parser.add_option('--sharedir', default=None, dest='staging_sharedir',
        help='Location where calibre resources were installed, typically /usr/share/calibre')

    return parser


def options(option_parser):
    parser = option_parser()
    options = parser.option_list
    for group in parser.option_groups:
        options += group.option_list
    opts = []
    for opt in options:
        opts.extend(opt._short_opts)
        opts.extend(opt._long_opts)
    return opts

def opts_and_words(name, op, words):
    opts  = '|'.join(options(op))
    words = '|'.join([w.replace("'", "\\'") for w in words])
    fname = name.replace('-', '_')
    return ('_'+fname+'()'+\
'''
{
    local cur opts
    local IFS=$'|\\t'
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    opts="%s"
    words="%s"

    case "${cur}" in
      -* )
         COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
         COMPREPLY=( $( echo ${COMPREPLY[@]} | sed 's/ /\\\\ /g' | tr '\\n' '\\t' ) )
         return 0
         ;;
      *  )
         COMPREPLY=( $(compgen -W "${words}" -- ${cur}) )
         COMPREPLY=( $( echo ${COMPREPLY[@]} | sed 's/ /\\\\ /g' | tr '\\n' '\\t' ) )
         return 0
         ;;
    esac

}
complete -F _'''%(opts, words) + fname + ' ' + name +"\n\n").encode('utf-8')


def opts_and_exts(name, op, exts):
    opts = ' '.join(options(op))
    exts.extend([i.upper() for i in exts])
    exts='|'.join(exts)
    fname = name.replace('-', '_')
    return '_'+fname+'()'+\
'''
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="%s"
    pics="@(jpg|jpeg|png|gif|bmp|JPG|JPEG|PNG|GIF|BMP)"

    case "${prev}" in
      --cover )
           _filedir "${pics}"
           return 0
           ;;
    esac

    case "${cur}" in
      --cover )
         _filedir "${pics}"
         return 0
         ;;
      -* )
         COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
         return 0
         ;;
      *  )
        _filedir '@(%s)'
        return 0
        ;;
    esac

}
complete -o filenames -F _'''%(opts,exts) + fname + ' ' + name +"\n\n"


VIEWER = '''\
[Desktop Entry]
Version=1.0
Type=Application
Name=LRF Viewer
GenericName=Viewer for LRF files
Comment=Viewer for LRF files (SONY ebook format files)
TryExec=lrfviewer
Exec=lrfviewer %F
Icon=calibre-viewer
MimeType=application/x-sony-bbeb;
Categories=Graphics;Viewer;
'''

EVIEWER = '''\
[Desktop Entry]
Version=1.0
Type=Application
Name=E-book Viewer
GenericName=Viewer for E-books
Comment=Viewer for E-books in all the major formats
TryExec=ebook-viewer
Exec=ebook-viewer %F
Icon=calibre-viewer
Categories=Graphics;Viewer;
'''


GUI = '''\
[Desktop Entry]
Version=1.0
Type=Application
Name=calibre
GenericName=E-book library management
Comment=E-book library management: Convert, view, share, catalogue all your e-books
TryExec=calibre
Exec=calibre
Icon=calibre-gui
Categories=Office;
'''

MIME = '''\
<?xml version="1.0"?>
<mime-info xmlns='http://www.freedesktop.org/standards/shared-mime-info'>
    <mime-type type="application/x-sony-bbeb">
        <comment>SONY E-book compiled format</comment>
        <glob pattern="*.lrf"/>
    </mime-type>
    <mime-type type="application/epub+zip">
        <comment>EPUB ebook format</comment>
        <glob pattern="*.epub"/>
    </mime-type>
    <mime-type type="text/lrs">
        <comment>SONY E-book source format</comment>
        <glob pattern="*.lrs"/>
    </mime-type>
</mime-info>
'''

def render_img(image, dest, width=128, height=128):
    from PyQt4.Qt import QImage, Qt
    img = QImage(I(image)).scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    img.save(dest)

def main():
    p = option_parser()
    opts, args = p.parse_args()
    PostInstall(opts)
    return 0


if __name__ == '__main__':
    sys.exit(main())
