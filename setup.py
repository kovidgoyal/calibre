from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re, os, subprocess
sys.path.append('src')
iswindows = re.search('win(32|64)', sys.platform)
isosx = 'darwin' in sys.platform
islinux = not isosx and not iswindows
src = open('src/calibre/constants.py', 'rb').read()
VERSION = re.search(r'__version__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
APPNAME = re.search(r'__appname__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
print 'Setup', APPNAME, 'version:', VERSION

epsrc = re.compile(r'entry_points = (\{.*?\})', re.DOTALL).search(open('src/%s/linux.py'%APPNAME, 'rb').read()).group(1)
entry_points = eval(epsrc, {'__appname__': APPNAME})

def _ep_to_script(ep, base='src'):
    return (base+os.path.sep+re.search(r'.*=\s*(.*?):', ep).group(1).replace('.', '/')+'.py').strip()


scripts = {
           'console' : [_ep_to_script(i) for i in entry_points['console_scripts']],
           'gui' : [_ep_to_script(i) for i in entry_points['gui_scripts']],
          }

def _ep_to_basename(ep):
    return re.search(r'\s*(.*?)\s*=', ep).group(1).strip()
basenames = {
             'console' : [_ep_to_basename(i) for i in entry_points['console_scripts']],
             'gui' : [_ep_to_basename(i) for i in entry_points['gui_scripts']],
            }

def _ep_to_module(ep):
    return re.search(r'.*=\s*(.*?)\s*:', ep).group(1).strip()
main_modules = {
                'console' : [_ep_to_module(i) for i in entry_points['console_scripts']],
                'gui' : [_ep_to_module(i) for i in entry_points['gui_scripts']],
               }

def _ep_to_function(ep):
    return ep[ep.rindex(':')+1:].strip()
main_functions = {
                'console' : [_ep_to_function(i) for i in entry_points['console_scripts']],
                'gui' : [_ep_to_function(i) for i in entry_points['gui_scripts']],
               }

def setup_mount_helper():
    def warn():
        print 'WARNING: Failed to compile mount helper. Auto mounting of',
        print 'devices will not work'

    if os.geteuid() != 0:
        return warn()
    import stat
    src = os.path.join('src', 'calibre', 'devices', 'linux_mount_helper.c')
    dest = '/usr/bin/calibre-mount-helper'
    p = subprocess.Popen(['gcc', '-Wall', src, '-o', dest])
    ret = p.wait()
    if ret != 0:
        return warn()
    os.chown(dest, 0, 0)
    os.chmod(dest,
       stat.S_ISUID|stat.S_ISGID|stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)

if __name__ == '__main__':
    from setuptools import setup, find_packages
    from pyqtdistutils import PyQtExtension, build_ext, Extension, QMAKE
    from upload import sdist, pot, build, build_py, manual, \
                        resources, clean, gui, translations, update, \
                        tag_release, upload_demo, build_linux, build_windows, \
                        build_osx, upload_installers, upload_user_manual, \
                        upload_to_pypi, stage3, stage2, stage1, upload, \
                        upload_rss, betas, build_linux32, build_linux64, \
                        build_osx64, get_translations
    resources.SCRIPTS = {}
    for x in ('console', 'gui'):
        for name in basenames[x]:
            resources.SCRIPTS[name] = x

    list(basenames['console']+basenames['gui'])

    entry_points['console_scripts'].append(
                            'calibre_postinstall = calibre.linux:post_install')
    optional = []
    def qmake_query(arg=''):
        cmd = [QMAKE, '-query']
        if arg:
            cmd += [arg]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout.read()
    qt_inc = qt_lib = None
    qt_inc = qmake_query('QT_INSTALL_HEADERS').splitlines()[0]
    qt_inc = qt_inc if qt_inc not in ('', '**Unknown**') and os.path.isdir(qt_inc) else None
    qt_lib = qmake_query('QT_INSTALL_LIBS').splitlines()[0]
    qt_lib = qt_lib if qt_lib not in ('', '**Unknown**') and os.path.isdir(qt_lib) else None
    if qt_lib is None or qt_inc is None:
        print '\n\nWARNING: Could not find QT librariers and headers.',
        print 'Is qmake in your PATH?\n\n'


    if iswindows:
        optional.append(Extension('calibre.plugins.winutil',
                sources=['src/calibre/utils/windows/winutil.c'],
                libraries=['shell32', 'setupapi'],
                include_dirs=os.environ.get('INCLUDE',
                        'C:/WinDDK/6001.18001/inc/api/;'
                        'C:/WinDDK/6001.18001/inc/crt/').split(';'),
                extra_compile_args=['/X']
                ))

    poppler_inc = '/usr/include/poppler/qt4'
    poppler_lib = '/usr/lib'
    poppler_libs = []
    if iswindows:
        poppler_inc = r'C:\cygwin\home\kovid\poppler\include\poppler\qt4'
        poppler_lib = r'C:\cygwin\home\kovid\poppler\lib'
        poppler_libs = ['QtCore4', 'QtGui4']
    if isosx:
        poppler_inc = '/Volumes/sw/build/poppler-0.10.7/qt4/src'
        poppler_lib = '/Users/kovid/poppler/lib'
    poppler_inc = os.environ.get('POPPLER_INC_DIR', poppler_inc)
    if os.path.exists(os.path.join(poppler_inc, 'poppler-qt4.h'))\
            and qt_lib is not None and qt_inc is not None:
        optional.append(Extension('calibre.plugins.calibre_poppler',
                        sources=['src/calibre/utils/poppler/poppler.cpp'],
                        libraries=(['poppler', 'poppler-qt4']+poppler_libs),
                        library_dirs=[os.environ.get('POPPLER_LIB_DIR',
                            poppler_lib), qt_lib],
                        include_dirs=[poppler_inc, qt_inc]))
    else:
        print '\n\nWARNING: Poppler not found on your system. Various PDF related',
        print 'functionality will not work. Use the POPPLER_INC_DIR and',
        print 'POPPLER_LIB_DIR environment variables.\n\n'

    podofo_inc = '/usr/include/podofo' if islinux else \
    'C:\\podofo\\include\\podofo' if iswindows else \
    '/usr/local/include/podofo'
    podofo_lib = '/usr/lib' if islinux else r'C:\podofo' if iswindows else \
            '/usr/local/lib'
    podofo_inc = os.environ.get('PODOFO_INC_DIR', podofo_inc)
    if os.path.exists(os.path.join(podofo_inc, 'podofo.h')):
        optional.append(Extension('calibre.plugins.podofo',
                        sources=['src/calibre/utils/podofo/podofo.cpp'],
                        libraries=['podofo'],
                        library_dirs=[os.environ.get('PODOFO_LIB_DIR', podofo_lib)],
                        include_dirs=[podofo_inc]))
    else:
        print '\n\nWARNING: PoDoFo not found on your system. Various PDF related',
        print 'functionality will not work. Use the PODOFO_INC_DIR and',
        print 'PODOFO_LIB_DIR environment variables.\n\n'

    fc_inc = '/usr/include/fontconfig' if islinux else \
            r'C:\cygwin\home\kovid\fontconfig\include\fontconfig' if iswindows else \
            '/Users/kovid/fontconfig/include/fontconfig'
    fc_lib = '/usr/lib' if islinux else \
            r'C:\cygwin\home\kovid\fontconfig\lib' if iswindows else \
            '/Users/kovid/fontconfig/lib'

    fc_inc = os.environ.get('FC_INC_DIR', fc_inc)
    fc_lib = os.environ.get('FC_LIB_DIR', fc_lib)
    if not os.path.exists(os.path.join(fc_inc, 'fontconfig.h')):
        print '\n\nERROR: fontconfig not found on your system.',
        print 'Use the FC_INC_DIR and FC_LIB_DIR environment variables.\n\n'
        raise SystemExit(1)
    ext_modules = optional + [

                   Extension('calibre.plugins.fontconfig',
                       sources = ['src/calibre/utils/fonts/fontconfig.c'],
                       include_dirs = [fc_inc],
                       libraries=['fontconfig'],
                       library_dirs=[fc_lib]),

                   Extension('calibre.plugins.lzx',
                             sources=['src/calibre/utils/lzx/lzxmodule.c',
                                      'src/calibre/utils/lzx/compressor.c',
                                      'src/calibre/utils/lzx/lzxd.c',
                                      'src/calibre/utils/lzx/lzc.c',
                                      'src/calibre/utils/lzx/lzxc.c'],
                             include_dirs=['src/calibre/utils/lzx']),

                   Extension('calibre.plugins.msdes',
                             sources=['src/calibre/utils/msdes/msdesmodule.c',
                                      'src/calibre/utils/msdes/des.c'],
                             include_dirs=['src/calibre/utils/msdes']),

                    Extension('calibre.plugins.cPalmdoc',
                        sources=['src/calibre/ebooks/compression/palmdoc.c']),

                    PyQtExtension('calibre.plugins.pictureflow',
                                  ['src/calibre/gui2/pictureflow/pictureflow.cpp',
                                   'src/calibre/gui2/pictureflow/pictureflow.h'],
                                   ['src/calibre/gui2/pictureflow/pictureflow.sip']
                                  )
                 ]
    if isosx:
        ext_modules.append(Extension('calibre.plugins.usbobserver',
                sources=['src/calibre/devices/usbobserver/usbobserver.c'],
                extra_link_args=['-framework', 'IOKit'])
                           )

    if not iswindows:
        plugins = ['plugins/%s.so'%(x.name.rpartition('.')[-1]) for x in ext_modules]
    else:
        plugins = ['plugins/%s.pyd'%(x.name.rpartition('.')[-1]) for x in ext_modules] + \
                  ['plugins/%s.pyd.manifest'%(x.name.rpartition('.')[-1]) \
                        for x in ext_modules if 'pictureflow' not in x.name]


    setup(
          name           = APPNAME,
          packages       = find_packages('src'),
          package_dir    = { '' : 'src' },
          version        = VERSION,
          author         = 'Kovid Goyal',
          author_email   = 'kovid@kovidgoyal.net',
          url            = 'http://%s.kovidgoyal.net'%APPNAME,
          package_data   = {'calibre':plugins},
          entry_points   = entry_points,
          zip_safe       = False,
          options        = { 'bdist_egg' : {'exclude_source_files': True,}, },
          ext_modules    = ext_modules,
          description    =
                      '''
                      E-book management application.
                      ''',
          long_description =
          '''
  %s is an e-book library manager. It can view, convert and catalog e-books \
  in most of the major e-book formats. It can also talk to e-book reader \
  devices. It can go out to the internet and fetch metadata for your books. \
  It can download newspapers and convert them into e-books for convenient \
  reading. It is cross platform, running on Linux, Windows and OS X.

  For screenshots: https://%s.kovidgoyal.net/wiki/Screenshots

  For installation/usage instructions please see
  http://%s.kovidgoyal.net

  For source code access:
  bzr branch lp:%s

  To update your copy of the source code:
  bzr merge

          '''%(APPNAME, APPNAME, APPNAME, APPNAME),
          license = 'GPL',
          classifiers    = [
            'Development Status :: 4 - Beta',
            'Environment :: Console',
            'Environment :: X11 Applications :: Qt',
            'Intended Audience :: Developers',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Natural Language :: English',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: System :: Hardware :: Hardware Drivers'
            ],
          cmdclass       = {
                      'build_ext'     : build_ext,
                      'build'         : build,
                      'build_py'      : build_py,
                      'pot'           : pot,
                      'manual'        : manual,
                      'resources'     : resources,
                      'translations'  : translations,
                      'get_translations': get_translations,
                      'gui'           : gui,
                      'clean'         : clean,
                      'sdist'         : sdist,
                      'update'        : update,
                      'tag_release'   : tag_release,
                      'upload_demo'   : upload_demo,
                      'build_linux'   : build_linux,
                      'build_linux32'  : build_linux32,
                      'build_linux64' : build_linux64,
                      'build_windows' : build_windows,
                      'build_osx'     : build_osx,
                      'build_osx64'   : build_osx64,
                      'upload_installers': upload_installers,
                      'upload_user_manual': upload_user_manual,
                      'upload_to_pypi': upload_to_pypi,
                      'upload_rss'    : upload_rss,
                      'stage3' : stage3,
                      'stage2' : stage2,
                      'stage1' : stage1,
                      'publish' : upload,
                      'betas'  : betas,
                      },
         )

    if 'develop' in ' '.join(sys.argv) and islinux:
        subprocess.check_call('calibre_postinstall --do-not-reload-udev-hal', shell=True)
        setup_mount_helper()
    if 'install' in sys.argv and islinux:
        subprocess.check_call('calibre_postinstall', shell=True)
        setup_mount_helper()
