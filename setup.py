#!/usr/bin/env python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re, os, shutil
sys.path.append('src')
iswindows = re.search('win(32|64)', sys.platform)
isosx = 'darwin' in sys.platform
islinux = not isosx and not iswindows
src = open('src/calibre/__init__.py', 'rb').read()
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
    from setuptools import setup, find_packages, Extension
    from pyqtdistutils import PyQtExtension, build_ext
    import subprocess, glob
    
    entry_points['console_scripts'].append('calibre_postinstall = calibre.linux:post_install')
    ext_modules = [
                   Extension('calibre.plugins.lzx',
                             sources=['src/calibre/utils/lzx/lzxmodule.c',
                                      'src/calibre/utils/lzx/lzxd.c'],
                             include_dirs=['src/calibre/utils/lzx']),
                   Extension('calibre.plugins.msdes',
                             sources=['src/calibre/utils/msdes/msdesmodule.c',
                                      'src/calibre/utils/msdes/des.c'],
                             include_dirs=['src/calibre/utils/msdes']),
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
                include_dirs=['C:/WinDDK/6001.18001/inc/api/'])
                           )
    if isosx:
        ext_modules.append(Extension('calibre.plugins.usbobserver',
                sources=['src/calibre/devices/usbobserver/usbobserver.c'])
                           )
    
    setup(
          name=APPNAME,
          packages = find_packages('src'),
          package_dir = { '' : 'src' },
          version=VERSION,
          author='Kovid Goyal',
          author_email='kovid@kovidgoyal.net',
          url = 'http://%s.kovidgoyal.net'%APPNAME,
          package_data = {'calibre':['plugins/*']},
          include_package_data=True,
          entry_points = entry_points,
          zip_safe = False,
          options = { 'bdist_egg' : {'exclude_source_files': True,}, },
          ext_modules=ext_modules,
          description =
                      '''
                      E-book management application.
                      ''',
          long_description =
          '''
  %s is an e-book library manager. It can view, convert and catalog e-books in most of the major e-book formats. It can also talk to a few e-book reader devices. It can go out to the internet and fetch metadata for your books. It can download newspapers and convert them into e-books for convenient reading. It is cross platform, running on Linux, Windows and OS X.

  For screenshots: https://%s.kovidgoyal.net/wiki/Screenshots

  For installation/usage instructions please see
  http://%s.kovidgoyal.net

  For source code access:
  bzr branch http://bzr.kovidgoyal.net/code/%s/trunk %s

  To update your copy of the source code:
  bzr merge

          '''%(APPNAME, APPNAME, APPNAME, APPNAME, APPNAME),
          license = 'GPL',
          classifiers = [
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
          cmdclass = {'build_ext': build_ext},
         )

    if 'develop' in ' '.join(sys.argv) and islinux:
        subprocess.check_call('calibre_postinstall', shell=True)
