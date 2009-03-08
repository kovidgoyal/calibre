__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Post installation script for linux '''
import sys, os, re, shutil
from subprocess import check_call, call
from tempfile import NamedTemporaryFile

from calibre import __version__, __appname__
from calibre.devices import devices

DEVICES = devices()

DESTDIR = ''
if os.environ.has_key('DESTDIR'):
    DESTDIR = os.environ['DESTDIR']

entry_points = {
        'console_scripts': [ \
             'ebook-device       = calibre.devices.prs500.cli.main:main',
             'ebook-meta         = calibre.ebooks.metadata.cli:main',
             'ebook-convert      = calibre.ebooks.convert.cli:main',
             'txt2lrf            = calibre.ebooks.lrf.txt.convert_from:main',
             'html2lrf           = calibre.ebooks.lrf.html.convert_from:main',
             'html2oeb           = calibre.ebooks.html:main',
             'html2epub          = calibre.ebooks.epub.from_html:main',
             'odt2oeb            = calibre.ebooks.odt.to_oeb:main',
             'markdown-calibre   = calibre.ebooks.markdown.markdown:main',
             'lit2lrf            = calibre.ebooks.lrf.lit.convert_from:main',
             'epub2lrf           = calibre.ebooks.lrf.epub.convert_from:main',
             'rtf2lrf            = calibre.ebooks.lrf.rtf.convert_from:main',
             'web2disk           = calibre.web.fetch.simple:main',
             'feeds2disk         = calibre.web.feeds.main:main',
             'calibre-server     = calibre.library.server:main',
             'feeds2lrf          = calibre.ebooks.lrf.feeds.convert_from:main',
             'feeds2epub         = calibre.ebooks.epub.from_feeds:main',
             'feeds2mobi         = calibre.ebooks.mobi.from_feeds:main',
             'web2lrf            = calibre.ebooks.lrf.web.convert_from:main',
             'pdf2lrf            = calibre.ebooks.lrf.pdf.convert_from:main',
             'mobi2lrf           = calibre.ebooks.lrf.mobi.convert_from:main',
             'fb22lrf            = calibre.ebooks.lrf.fb2.convert_from:main',
             'any2lrf            = calibre.ebooks.lrf.any.convert_from:main',
             'any2epub           = calibre.ebooks.epub.from_any:main',
             'any2lit            = calibre.ebooks.lit.from_any:main',
             'any2mobi           = calibre.ebooks.mobi.from_any:main',
             'lrf2lrs            = calibre.ebooks.lrf.lrfparser:main',
             'lrs2lrf            = calibre.ebooks.lrf.lrs.convert_from:main',
             'pdfreflow          = calibre.ebooks.lrf.pdf.reflow:main',
             'isbndb             = calibre.ebooks.metadata.isbndb:main',
             'librarything       = calibre.ebooks.metadata.library_thing:main',
             'mobi2oeb           = calibre.ebooks.mobi.reader:main',
             'oeb2mobi           = calibre.ebooks.mobi.writer:main',
             'lit2oeb            = calibre.ebooks.lit.reader:main',
             'oeb2lit            = calibre.ebooks.lit.writer:main',
             'comic2lrf          = calibre.ebooks.lrf.comic.convert_from:main',
             'comic2epub         = calibre.ebooks.epub.from_comic:main',
             'comic2mobi         = calibre.ebooks.mobi.from_comic:main',
             'comic2pdf          = calibre.ebooks.pdf.from_comic:main',
             'calibre-debug      = calibre.debug:main',
             'calibredb          = calibre.library.cli:main',
             'calibre-fontconfig = calibre.utils.fontconfig:main',
             'calibre-parallel   = calibre.parallel:main',
             'calibre-customize  = calibre.customize.ui:main',
             'pdftrim            = calibre.ebooks.pdf.pdftrim:main' ,
             'any2pdf  = calibre.ebooks.pdf.from_any:main',
        ],
        'gui_scripts'    : [
            __appname__+' = calibre.gui2.main:main',
            'lrfviewer    = calibre.gui2.lrf_renderer.main:main',
            'ebook-viewer = calibre.gui2.viewer.main:main',
                            ],
      }


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
    return '_'+name+'()'+\
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
complete -F _'''%(opts, words) + name + ' ' + name +"\n\n"


def opts_and_exts(name, op, exts):
    opts = ' '.join(options(op))
    exts.extend([i.upper() for i in exts])
    exts='|'.join(exts)
    return '_'+name+'()'+\
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
complete -o filenames -F _'''%(opts,exts) + name + ' ' + name +"\n\n"

use_destdir = False

def open_file(path, mode='wb'):
    if use_destdir:
        if os.path.isabs(path):
            path = path[1:]
        path = os.path.join(DESTDIR, path)
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    return open(path, mode)

def setup_completion(fatal_errors):
    try:
        print 'Setting up bash completion...',
        sys.stdout.flush()
        from calibre.ebooks.lrf.html.convert_from import option_parser as htmlop
        from calibre.ebooks.lrf.txt.convert_from import option_parser as txtop
        from calibre.ebooks.metadata.cli import option_parser as metaop, filetypes as meta_filetypes
        from calibre.ebooks.lrf.lrfparser import option_parser as lrf2lrsop
        from calibre.gui2.lrf_renderer.main import option_parser as lrfviewerop
        from calibre.ebooks.lrf.pdf.reflow import option_parser as pdfhtmlop
        from calibre.ebooks.mobi.reader import option_parser as mobioeb
        from calibre.ebooks.lit.reader import option_parser as lit2oeb
        from calibre.web.feeds.main import option_parser as feeds2disk
        from calibre.web.feeds.recipes import titles as feed_titles
        from calibre.ebooks.lrf.feeds.convert_from import option_parser as feeds2lrf
        from calibre.ebooks.lrf.comic.convert_from import option_parser as comicop
        from calibre.ebooks.epub.from_html import option_parser as html2epub
        from calibre.ebooks.html import option_parser as html2oeb
        from calibre.ebooks.odt.to_oeb import option_parser as odt2oeb
        from calibre.ebooks.epub.from_feeds import option_parser as feeds2epub
        from calibre.ebooks.mobi.from_feeds import option_parser as feeds2mobi
        from calibre.ebooks.epub.from_any import option_parser as any2epub
        from calibre.ebooks.lit.from_any import option_parser as any2lit
        from calibre.ebooks.epub.from_comic import option_parser as comic2epub
        from calibre.ebooks.mobi.from_any import option_parser as any2mobi
        from calibre.ebooks.mobi.writer import option_parser as oeb2mobi
        from calibre.gui2.main import option_parser as guiop 
        any_formats = ['epub', 'htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip',
             'txt', 'lit', 'rtf', 'pdf', 'prc', 'mobi', 'fb2', 'odt'] 
        f = open_file('/etc/bash_completion.d/libprs500')
        f.close()
        os.remove(f.name)
        manifest = []
        f = open_file('/etc/bash_completion.d/calibre')
        manifest.append(f.name)

        f.write('# calibre Bash Shell Completion\n')
        f.write(opts_and_exts('html2lrf', htmlop,
                              ['htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip', 'php']))
        f.write(opts_and_exts('txt2lrf', txtop, ['txt']))
        f.write(opts_and_exts('lit2lrf', htmlop, ['lit']))
        f.write(opts_and_exts('epub2lrf', htmlop, ['epub']))
        f.write(opts_and_exts('rtf2lrf', htmlop, ['rtf']))
        f.write(opts_and_exts('mobi2lrf', htmlop, ['mobi', 'prc']))
        f.write(opts_and_exts('fb22lrf', htmlop, ['fb2']))
        f.write(opts_and_exts('pdf2lrf', htmlop, ['pdf']))
        f.write(opts_and_exts('any2lrf', htmlop, any_formats))
        f.write(opts_and_exts('calibre', guiop, any_formats))
        f.write(opts_and_exts('any2epub', any2epub, any_formats))
        f.write(opts_and_exts('any2lit', any2lit, any_formats))
        f.write(opts_and_exts('any2mobi', any2mobi, any_formats))
        f.write(opts_and_exts('oeb2mobi', oeb2mobi, ['opf']))
        f.write(opts_and_exts('lrf2lrs', lrf2lrsop, ['lrf']))
        f.write(opts_and_exts('ebook-meta', metaop, list(meta_filetypes())))
        f.write(opts_and_exts('lrfviewer', lrfviewerop, ['lrf']))
        f.write(opts_and_exts('pdfrelow', pdfhtmlop, ['pdf']))
        f.write(opts_and_exts('mobi2oeb', mobioeb, ['mobi', 'prc']))
        f.write(opts_and_exts('lit2oeb', lit2oeb, ['lit']))
        f.write(opts_and_exts('comic2lrf', comicop, ['cbz', 'cbr']))
        f.write(opts_and_exts('comic2epub', comic2epub, ['cbz', 'cbr']))
        f.write(opts_and_exts('comic2mobi', comic2epub, ['cbz', 'cbr']))
        f.write(opts_and_exts('comic2pdf', comic2epub, ['cbz', 'cbr']))
        f.write(opts_and_words('feeds2disk', feeds2disk, feed_titles))
        f.write(opts_and_words('feeds2lrf', feeds2lrf, feed_titles))
        f.write(opts_and_words('feeds2epub', feeds2epub, feed_titles))
        f.write(opts_and_words('feeds2mobi', feeds2mobi, feed_titles))
        f.write(opts_and_exts('html2epub', html2epub, ['html', 'htm', 'xhtm', 'xhtml', 'opf']))
        f.write(opts_and_exts('html2oeb', html2oeb, ['html', 'htm', 'xhtm', 'xhtml']))
        f.write(opts_and_exts('odt2oeb', odt2oeb, ['odt']))
        f.write('''
_prs500_ls()
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

  listing="$(prs500 ls ${search} 2>/dev/null)"

  prefix="${search}"
  if [[ "x${prefix:(-1)}" != "x/" ]]; then
    prefix="${prefix}/"
  fi

  echo $(compgen -P "${prefix}" -W "${listing}" "${pattern}")
}

_prs500()
{
  local cur prev
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  COMPREPLY=()
  case "${prev}" in
    ls|rm|mkdir|touch|cat )
        COMPREPLY=( $(_prs500_ls "${cur}") )
        return 0
        ;;
    cp )
        if [[ ${cur} == prs500:* ]]; then
          COMPREPLY=( $(_prs500_ls "${cur:7}") )
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
          COMPREPLY=( $(_prs500_ls "${cur:7}") )
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
complete -o nospace  -F _prs500 prs500

''')
        f.close()
        print 'done'
    except TypeError, err:
        if 'resolve_entities' in str(err):
            print 'You need python-lxml >= 2.0.5 for calibre'
            sys.exit(1)
        raise
    except:
        if fatal_errors:
            raise
        print 'failed'
        import traceback
        traceback.print_exc()
    return manifest

def setup_udev_rules(group_file, reload, fatal_errors):
    print 'Trying to setup udev rules...'
    manifest = []
    sys.stdout.flush()
    groups = open(group_file, 'rb').read()
    group = 'plugdev' if 'plugdev' in groups else 'usb'
    udev = open_file('/etc/udev/rules.d/95-calibre.rules')
    manifest.append(udev.name)
    udev.write('''# Sony Reader PRS-500\n'''
               '''BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", MODE="660", GROUP="%s"\n'''%(group,)
             )
    udev.close()
    fdi = open_file('/usr/share/hal/fdi/policy/20thirdparty/10-calibre.fdi')
    manifest.append(fdi.name)
    fdi.write('<?xml version="1.0" encoding="UTF-8"?>\n\n<deviceinfo version="0.2">\n')
    for cls in DEVICES:
        fdi.write(\
'''
  <device>
      <match key="usb_device.vendor_id" int="%(vendor_id)s">
          <match key="usb_device.product_id" int="%(product_id)s">
              <match key="usb_device.device_revision_bcd" int="%(bcd)s">
                  <merge key="calibre.deviceclass" type="string">%(cls)s</merge>
              </match>
          </match>
      </match>
  </device>
'''%dict(cls=cls.__name__, vendor_id=cls.VENDOR_ID, product_id=cls.PRODUCT_ID,
         prog=__appname__, bcd=cls.BCD))
        fdi.write('\n'+cls.get_fdi())
    fdi.write('\n</deviceinfo>\n')
    fdi.close()
    if reload:
        called = False
        for hal in ('hald', 'hal', 'haldaemon'):
            hal = os.path.join('/etc/init.d', hal)
            if os.access(hal, os.X_OK):
                call((hal, 'restart'))
                called = True
                break
        if not called and os.access('/etc/rc.d/rc.hald', os.X_OK):
            call(('/etc/rc.d/rc.hald', 'restart'))

        try:
            check_call('udevadm control --reload_rules', shell=True)
        except:
            try:
                check_call('udevcontrol reload_rules', shell=True)
            except:
                try:
                    check_call('/etc/init.d/udev reload', shell=True)
                except:
                    if fatal_errors:
                        raise Exception("Couldn't reload udev, you may have to reboot")
                    print >>sys.stderr, "Couldn't reload udev, you may have to reboot"
    return manifest

def option_parser():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('--use-destdir', action='store_true', default=False, dest='destdir',
                      help='If set, respect the environment variable DESTDIR when installing files')
    parser.add_option('--do-not-reload-udev-hal', action='store_true', dest='dont_reload', default=False,
                      help='If set, do not try to reload udev rules and HAL FDI files')
    parser.add_option('--group-file', default='/etc/group', dest='group_file',
                      help='File from which to read group information. Default: %default')
    parser.add_option('--dont-check-root', action='store_true', default=False, dest='no_root',
                      help='If set, do not check if we are root.')
    parser.add_option('--make-errors-fatal', action='store_true', default=False,
                      dest='fatal_errors', help='If set die on errors.')
    parser.add_option('--save-manifest-to', default=None,
                      help='Save a manifest of all installed files to the specified location')
    return parser

def install_man_pages(fatal_errors):
    from bz2 import compress
    import subprocess
    print 'Installing MAN pages...'
    manpath = '/usr/share/man/man1'
    f = NamedTemporaryFile()
    f.write('[see also]\nhttp://%s.kovidgoyal.net\n'%__appname__)
    f.flush()
    manifest = []
    os.environ['PATH'] += ':'+os.path.expanduser('~/bin')
    for src in entry_points['console_scripts']:
        prog = src[:src.index('=')].strip()
        if prog in ('ebook-device', 'markdown-calibre', 
                    'calibre-fontconfig', 'calibre-parallel'):
            continue

        help2man = ('help2man', prog, '--name', 'part of %s'%__appname__,
                    '--section', '1', '--no-info', '--include',
                    f.name, '--manual', __appname__)
        manfile = os.path.join(manpath, prog+'.1'+__appname__+'.bz2')
        print '\tInstalling MAN page for', prog
        try:
            p = subprocess.Popen(help2man, stdout=subprocess.PIPE)
        except OSError, err:
            import errno
            if err.errno != errno.ENOENT:
                raise
            print 'Failed to install MAN pages as help2man is missing from your system'
            break
        o = p.stdout.read()
        raw = re.compile(r'^\.IP\s*^([A-Z :]+)$', re.MULTILINE).sub(r'.SS\n\1', o)
        if not raw.strip():
            print 'Unable to create MAN page for', prog
            continue
        f2 = open_file(manfile)
        manifest.append(f2.name)
        f2.write(compress(raw))
    return manifest

def post_install():
    parser = option_parser()
    opts = parser.parse_args()[0]

    global use_destdir
    use_destdir = opts.destdir
    manifest = []
    setup_desktop_integration(opts.fatal_errors)
    if opts.no_root or os.geteuid() == 0:
        manifest += setup_udev_rules(opts.group_file, not opts.dont_reload, opts.fatal_errors)
        manifest += setup_completion(opts.fatal_errors)
        manifest += install_man_pages(opts.fatal_errors)
    else:
        print "Skipping udev, completion, and man-page install for non-root user."

    try:
        from PyQt4 import Qt
        if Qt.PYQT_VERSION < int('0x40402', 16):
            print 'WARNING: You need PyQt >= 4.4.2 for the GUI. You have', Qt.PYQT_VERSION_STR, '\nYou may experience crashes or other strange behavior.'
    except ImportError:
        print 'WARNING: You do not have PyQt4 installed. The GUI will not work.'

    if opts.save_manifest_to:
        open(opts.save_manifest_to, 'wb').write('\n'.join(manifest)+'\n')
        
    from calibre.utils.config import config_dir
    if os.path.exists(config_dir):
        os.chdir(config_dir)
        for f in os.listdir('.'):
            if os.stat(f).st_uid == 0:
                os.unlink(f)

def binary_install():
    manifest = os.path.join(getattr(sys, 'frozen_path'), 'manifest')
    exes = [x.strip() for x in open(manifest).readlines()]
    print 'Creating symlinks...'
    for exe in exes:
        dest = os.path.join('/usr', 'bin', exe)
        if os.path.exists(dest):
            os.remove(dest)
        os.symlink(os.path.join(getattr(sys, 'frozen_path'), exe), dest)
    post_install()
    return 0

VIEWER = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=LRF Viewer
GenericName=Viewer for LRF files
Comment=Viewer for LRF files (SONY ebook format files)
TryExec=lrfviewer
Exec=lrfviewer %%F
Icon=calibre-viewer
MimeType=application/x-sony-bbeb;
Categories=Graphics;Viewer;
'''%(__version__,)

EVIEWER = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=E-book Viewer
GenericName=Viewer for E-books
Comment=Viewer for E-books
TryExec=ebook-viewer
Exec=ebook-viewer %%F
Icon=calibre-viewer
MimeType=application/epub+zip;
Categories=Graphics;Viewer;
'''%(__version__,)


GUI = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=calibre
GenericName=E-book library management
Comment=E-book library management
TryExec=calibre
Exec=calibre
Icon=calibre-gui
Categories=Office;
'''%(__version__,)

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

def render_svg(image, dest):
    from PyQt4.QtGui import QPainter, QImage
    from PyQt4.QtSvg import QSvgRenderer
    svg = QSvgRenderer(image.readAll())
    painter = QPainter()
    image = QImage(128,128,QImage.Format_ARGB32_Premultiplied)
    painter.begin(image)
    painter.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform|QPainter.HighQualityAntialiasing)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    svg.render(painter)
    painter.end()
    image.save(dest)

def setup_desktop_integration(fatal_errors):
    try:
        from PyQt4.QtCore import QFile
        from calibre.gui2 import images_rc # Load images
        from tempfile import mkdtemp

        print 'Setting up desktop integration...'


        tdir = mkdtemp()
        cwd = os.getcwdu()
        try:
            os.chdir(tdir)
            render_svg(QFile(':/images/mimetypes/lrf.svg'), os.path.join(tdir, 'calibre-lrf.png'))
            check_call('xdg-icon-resource install --context mimetypes --size 128 calibre-lrf.png application-lrf', shell=True)
            check_call('xdg-icon-resource install --context mimetypes --size 128 calibre-lrf.png text-lrs', shell=True)
            QFile(':library').copy(os.path.join(tdir, 'calibre-gui.png'))
            check_call('xdg-icon-resource install --size 128 calibre-gui.png calibre-gui', shell=True)
            render_svg(QFile(':/images/viewer.svg'), os.path.join(tdir, 'calibre-viewer.png'))
            check_call('xdg-icon-resource install --size 128 calibre-viewer.png calibre-viewer', shell=True)
            
            f = open('calibre-lrfviewer.desktop', 'wb')
            f.write(VIEWER)
            f.close()
            f = open('calibre-ebook-viewer.desktop', 'wb')
            f.write(EVIEWER)
            f.close()
            f = open('calibre-gui.desktop', 'wb')
            f.write(GUI)
            f.close()
            check_call('xdg-desktop-menu install ./calibre-gui.desktop ./calibre-lrfviewer.desktop', shell=True)
            f = open('calibre-mimetypes', 'wb')
            f.write(MIME)
            f.close()
            check_call('xdg-mime install calibre-mimetypes', shell=True)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tdir)
    except Exception, err:
        if fatal_errors:
            raise
        print >>sys.stderr, 'Could not setup desktop integration. Error:'
        print err

main = post_install
if __name__ == '__main__':
    post_install()




