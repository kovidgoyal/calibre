##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
import shutil
''' Post installation script for linux '''
import sys, os

from subprocess import check_call
from libprs500 import __version__, __appname__

from libprs500.devices import devices

DEVICES = devices()

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

def setup_completion():
    try:
        print 'Setting up bash completion...',
        sys.stdout.flush()
        from libprs500.ebooks.lrf.html.convert_from import option_parser as htmlop
        from libprs500.ebooks.lrf.txt.convert_from import option_parser as txtop
        from libprs500.ebooks.lrf.meta import option_parser as metaop
        from libprs500.ebooks.lrf.parser import option_parser as lrf2lrsop
        from libprs500.gui2.lrf_renderer.main import option_parser as lrfviewerop
        f = open('/etc/bash_completion.d/libprs500', 'wb')
        f.write('# libprs500 Bash Shell Completion\n')
        f.write(opts_and_exts('html2lrf', htmlop, 
                              ['htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip', 'php']))
        f.write(opts_and_exts('txt2lrf', txtop, ['txt']))
        f.write(opts_and_exts('lit2lrf', htmlop, ['lit']))
        f.write(opts_and_exts('rtf2lrf', htmlop, ['rtf']))
        f.write(opts_and_exts('pdf2lrf', htmlop, ['pdf']))
        f.write(opts_and_exts('any2lrf', htmlop, 
            ['htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip', 'txt', 'lit', 'rtf', 'pdf']))
        f.write(opts_and_exts('lrf2lrs', lrf2lrsop, ['lrf']))
        f.write(opts_and_exts('lrf-meta', metaop, ['lrf']))        
        f.write(opts_and_exts('rtf-meta', metaop, ['rtf']))
        f.write(opts_and_exts('pdf-meta', metaop, ['pdf']))
        f.write(opts_and_exts('lit-meta', metaop, ['lit']))
        f.write(opts_and_exts('lrfviewer', lrfviewerop, ['lrf']))
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
    except:
        print 'failed'
        import traceback
        traceback.print_exc()
        
def setup_udev_rules():
    print 'Trying to setup udev rules...'
    sys.stdout.flush()
    groups = open('/etc/group', 'rb').read()
    group = 'plugdev' if 'plugdev' in groups else 'usb'
    udev = open('/etc/udev/rules.d/95-libprs500.rules', 'w')
    udev.write('''# Sony Reader PRS-500\n'''
               '''BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", MODE="660", GROUP="%s"\n'''%(group,)
             )
    udev.close()
    fdi = open('/usr/share/hal/fdi/policy/20thirdparty/10-libprs500.fdi', 'w')
    fdi.write('<?xml version="1.0" encoding="UTF-8"?>\n\n<deviceinfo version="0.2">\n')
    for cls in DEVICES:
        fdi.write(\
'''
  <device>
      <match key="usb_device.vendor_id" int="%(vendor_id)s">
          <match key="usb_device.product_id" int="%(product_id)s">
              <merge key="libprs500.deviceclass" type="string">%(cls)s</merge>
          </match>
      </match>
  </device>
'''%dict(cls=cls.__name__, vendor_id=cls.VENDOR_ID, product_id=cls.PRODUCT_ID,
         prog=__appname__))
        fdi.write('\n'+cls.get_fdi())
    fdi.write('\n</deviceinfo>\n')
    fdi.close()
    try:
        check_call('/etc/init.d/hald restart', shell=True)
    except:
        check_call('/etc/init.d/hal restart', shell=True)
    
    try:
        check_call('udevcontrol reload_rules', shell=True)
    except:
        try:
            check_call('/etc/init.d/udev reload', shell=True)
        except:
            print >>sys.stderr, "Couldn't reload udev, you may have to reboot"

def post_install():
    if os.geteuid() != 0:
        print >> sys.stderr, 'You must be root to run this command.'
        sys.exit(1)
        
    setup_udev_rules()
    setup_completion()
    try:
        setup_desktop_integration()
    except:
        print >>sys.stderr, 'You do not have the Portland Desktop Utilities installed, skipping installation of desktop integration'
        
    try:
        from PyQt4 import Qt
        if Qt.PYQT_VERSION < int('0x40301', 16):
            print 'WARNING: You need PyQt >= 4.3.1 for the GUI. You have', Qt.PYQT_VERSION_STR, '\nYou may experience crashes or other strange behavior.'
    except ImportError:
        print 'WARNING: You do not have PyQt4 installed. The GUI will not work.'
    

    
VIEWER = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=LRF Viewer
Comment=Viewer for LRF files (SONY ebook format files)
TryExec=lrfviewer
Exec=lrfviewer %%F
Icon=libprs500-viewer
MimeType=application/x-sony-bbeb;
Categories=Graphics;Viewer;
'''%(__version__,)

GUI = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=Libprs500 - Ebook library management
Comment=E-book library management
TryExec=libprs500
Exec=libprs500
Icon=libprs500-gui
Categories=Office;
'''%(__version__,)

MIME = '''\
<?xml version="1.0"?>
<mime-info xmlns='http://www.freedesktop.org/standards/shared-mime-info'>
    <mime-type type="application/x-sony-bbeb">
        <comment>SONY E-book compiled format</comment>
        <glob pattern="*.lrf"/>
    </mime-type>
    <mime-type type="text/lrs">
        <comment>SONY E-book source format</comment>
        <glob pattern="*.lrs"/>
    </mime-type>
</mime-info>
'''

def setup_desktop_integration():
    from PyQt4.QtGui import QApplication, QPixmap  
    from PyQt4.QtCore import Qt
    from libprs500.gui2 import images_rc
    from tempfile import mkdtemp
    
    print 'Setting up desktop integration...'
    
    app = QApplication([])
    svg = QPixmap(':/images/mimetypes/lrf.svg').scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    gui = QPixmap(':library').scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    viewer = QPixmap(':/images/viewer.svg').scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)  
    tdir = mkdtemp()
    try:
        os.chdir(tdir)
        svg.save(os.path.join(tdir, 'libprs500-lrf.png'), 'PNG')
        gui.save(os.path.join(tdir, 'libprs500-gui.png'), 'PNG')
        viewer.save(os.path.join(tdir, 'libprs500-viewer.png'), 'PNG')
        check_call('xdg-icon-resource install --context mimetypes --size 128 libprs500-lrf.png application-lrf', shell=True)
        check_call('xdg-icon-resource install --context mimetypes --size 128 libprs500-lrf.png text-lrs', shell=True)
        check_call('xdg-icon-resource install --size 128 libprs500-gui.png libprs500-gui', shell=True)
        check_call('xdg-icon-resource install --size 128 libprs500-viewer.png libprs500-viewer', shell=True)
        f = open('libprs500-lrfviewer.desktop', 'wb')
        f.write(VIEWER)
        f.close()
        f = open('libprs500-gui.desktop', 'wb')
        f.write(GUI)
        f.close()
        check_call('xdg-desktop-menu install ./libprs500-gui.desktop ./libprs500-lrfviewer.desktop', shell=True)
        f = open('libprs500-mimetypes', 'wb')
        f.write(MIME)
        f.close()
        check_call('xdg-mime install libprs500-mimetypes', shell=True)
    finally:
        shutil.rmtree(tdir)
 
         
if __name__ == '__main__':
    post_install()           
    
    
      

