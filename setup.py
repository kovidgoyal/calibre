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

if __name__ == '__main__':
    from setuptools import setup, find_packages
    from pyqtdistutils import PyQtExtension, build_ext, Extension
    from upload import sdist, pot, build, build_py, manual, \
                        resources, clean, gui, translations, update, \
                        tag_release, upload_demo, build_linux, build_windows, \
                        build_osx, upload_installers, upload_user_manual, \
                        upload_to_pypi, stage3, stage2, stage1, upload, \
                        upload_rss

    entry_points['console_scripts'].append(
                            'calibre_postinstall = calibre.linux:post_install')
    optional = []


    podofo_inc = '/usr/include/podofo' if islinux else \
    'C:\\podofo\\include\\podofo' if iswindows else \
    '/Users/kovid/podofo/include/podofo'
    podofo_lib = '/usr/lib' if islinux else r'C:\podofo' if iswindows else \
            '/Users/kovid/podofo/lib'
    if os.path.exists(os.path.join(podofo_inc, 'podofo.h')):
        eca = ['/EHsc'] if iswindows else []
        optional.append(Extension('calibre.plugins.podofo',
                        sources=['src/calibre/utils/podofo/podofo.cpp'],
                        libraries=['podofo'], extra_compile_args=eca,
                        library_dirs=[os.environ.get('PODOFO_LIB_DIR', podofo_lib)],
                        include_dirs=\
                        [os.environ.get('PODOFO_INC_DIR', podofo_inc)]))

    ext_modules = optional + [

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
                        sources=['src/calibre/ebooks/mobi/palmdoc.c']),

                    PyQtExtension('calibre.plugins.pictureflow',
                                  ['src/calibre/gui2/pictureflow/pictureflow.cpp',
                                   'src/calibre/gui2/pictureflow/pictureflow.h'],
                                   ['src/calibre/gui2/pictureflow/pictureflow.sip']
                                  )
                 ]
    if iswindows:
        ext_modules.append(Extension('calibre.plugins.winutil',
                sources=['src/calibre/utils/windows/winutil.c'],
                libraries=['shell32', 'setupapi'],
                include_dirs=os.environ.get('INCLUDE',
                        'C:/WinDDK/6001.18001/inc/api/;'
                        'C:/WinDDK/6001.18001/inc/crt/').split(';'),
                extra_compile_args=['/X']
                ))
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
  bzr branch http://bzr.kovidgoyal.net/code/%s/trunk %s

  To update your copy of the source code:
  bzr merge

          '''%(APPNAME, APPNAME, APPNAME, APPNAME, APPNAME),
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
                      'gui'           : gui,
                      'clean'         : clean,
                      'sdist'         : sdist,
                      'update'        : update,
                      'tag_release'   : tag_release,
                      'upload_demo'   : upload_demo,
                      'build_linux'   : build_linux,
                      'build_windows' : build_windows,
                      'build_osx'     : build_osx,
                      'upload_installers': upload_installers,
                      'upload_user_manual': upload_user_manual,
                      'upload_to_pypi': upload_to_pypi,
                      'upload_rss'    : upload_rss,
                      'stage3' : stage3,
                      'stage2' : stage2,
                      'stage1' : stage1,
                      'publish' : upload,
                      },
         )

    if 'develop' in ' '.join(sys.argv) and islinux:
        subprocess.check_call('calibre_postinstall --do-not-reload-udev-hal', shell=True)
    if 'install' in sys.argv and islinux:
        subprocess.check_call('calibre_postinstall', shell=True)

