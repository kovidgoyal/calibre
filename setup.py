#!/usr/bin/env python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re, os, shutil
sys.path.append('src')
islinux = not ('win32' in sys.platform or 'win64' in sys.platform or 'darwin' in sys.platform)
src = open('src/calibre/__init__.py', 'rb').read()
VERSION = re.search(r'__version__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
APPNAME = re.search(r'__appname__\s+=\s+[\'"]([^\'"]+)[\'"]', src).group(1)
print 'Setup', APPNAME, 'version:', VERSION

epsrc = re.compile(r'entry_points = (\{.*?\})', re.DOTALL).search(open('src/%s/linux.py'%APPNAME, 'rb').read()).group(1)
entry_points = eval(epsrc, {'__appname__': APPNAME})

if 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower():
    entry_points['console_scripts'].append('parallel = %s.parallel:main'%APPNAME)

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
    import subprocess
    
    entry_points['console_scripts'].append('calibre_postinstall = calibre.linux:post_install')
    
    setup(
          name=APPNAME, 
          packages = find_packages('src'), 
          package_dir = { '' : 'src' }, 
          version=VERSION, 
          author='Kovid Goyal', 
          author_email='kovid@kovidgoyal.net', 
          url = 'http://%s.kovidgoyal.net'%APPNAME, 
          include_package_data = True,
          entry_points = entry_points, 
          zip_safe = True,
          description = 
                      """
                      Ebook management application.
                      """, 
          long_description = 
          """
  %s is an e-book library manager. It can view, convert and catalog e-books in most of the major e-book formats. It can also talk to a few e-book reader devices. It can go out to the internet and fetch metadata for your books. It can download newspapers and convert them into e-books for convenient reading. It is cross platform, running on Linux, Windows and OS X.
  
  For screenshots: https://%s.kovidgoyal.net/wiki/Screenshots
  
  For installation/usage instructions please see 
  http://%s.kovidgoyal.net
  
  For source code access: 
  bzr branch http://bzr.kovidgoyal.net/code/%s/trunk %s 
  
  To update your copy of the source code: 
  bzr merge
            
          """%(APPNAME, APPNAME, APPNAME, APPNAME, APPNAME),
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
            ]
         )
    
    if 'develop' in ' '.join(sys.argv) and islinux:
        subprocess.check_call('calibre_postinstall', shell=True)
