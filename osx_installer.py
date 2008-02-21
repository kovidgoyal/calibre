#!/usr/bin/env python
##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
''' Create an OSX installer '''

import sys, re, os, shutil, subprocess, stat
from setup import VERSION, APPNAME, scripts, main_modules, basenames, main_functions
from setuptools import setup
from py2app.build_app import py2app
from modulegraph.find_modules import find_modules

class BuildAPP(py2app):
    QT_PREFIX = '/Users/kovid/qt'
    LOADER_TEMPLATE = \
r'''#!/usr/bin/env python
import os, sys, glob
path = os.path.abspath(os.path.realpath(__file__))
dirpath = os.path.dirname(path)
name = os.path.basename(path)
base_dir = os.path.dirname(dirpath)
frameworks_dir = os.path.join(base_dir, 'Frameworks')
base_name = os.path.splitext(name)[0]
python = os.path.join(base_dir, 'MacOS', 'python')
loader_path = os.path.join(dirpath, base_name+'.py')
loader = open(loader_path, 'w')
site_packages = glob.glob(dirpath+'/*/*/site-packages.zip')[0]
print >>loader, '#!'+python
print >>loader, 'import sys'
print >>loader, 'sys.path.append(', repr(site_packages), ')'
print >>loader, 'sys.frozen = "macosx_app"'
print >>loader, 'sys.frameworks_dir =', repr(frameworks_dir)
print >>loader, 'import os'
print >>loader, 'base =', repr(dirpath)
print >>loader, 'from %(module)s import %(function)s'
print >>loader, '%(function)s()'
loader.close()
os.chmod(loader_path, 0700)
os.environ['PYTHONHOME'] = dirpath
os.execv(loader_path, sys.argv)
    '''
    CHECK_SYMLINKS_PRESCRIPT = \
r'''
def _check_symlinks_prescript():
    import os, tempfile, traceback, sys
    from Authorization import Authorization, kAuthorizationFlagDestroyRights
    
    AUTHTOOL="""#!%(sp)s
import os
scripts = %(sp)s
links = %(sp)s
os.setuid(0)
for s, l in zip(scripts, links):
    if os.path.lexists(l):
        os.remove(l)
    print 'Creating link:', l, '->', s
    os.symlink(s, l)
"""
    
    dest_path = %(dest_path)s
    resources_path = os.environ['RESOURCEPATH']
    scripts = %(scripts)s    
    links   = [os.path.join(dest_path, i) for i in scripts]
    scripts = [os.path.join(resources_path, i) for i in scripts]
    
    bad = False
    for s, l in zip(scripts, links):
        if os.path.exists(l) and os.path.exists(os.path.realpath(l)):
            continue
        bad = True
        break
    if bad:
        auth = Authorization(destroyflags=(kAuthorizationFlagDestroyRights,))
        fd, name = tempfile.mkstemp('.py')
        os.write(fd, AUTHTOOL %(pp)s (sys.executable, repr(scripts), repr(links)))
        os.close(fd)
        os.chmod(name, 0700)
        try:
            pipe = auth.executeWithPrivileges(name)
            sys.stdout.write(pipe.read())
            pipe.close()
        except:
            traceback.print_exc()
        finally:
            os.unlink(name)
_check_symlinks_prescript()
'''
    def get_modulefinder(self):
        if self.debug_modulegraph:
            debug = 4
        else:
            debug = 0
        return find_modules(
            scripts=scripts['console'] + scripts['gui'],
            includes=list(self.includes) + main_modules['console'],
            packages=self.packages,
            excludes=self.excludes,
            debug=debug,
        )
        
    @classmethod
    def makedmg(cls, d, volname, 
                destdir='dist', 
                internet_enable=True,
                format='UDBZ'):
        ''' Copy a directory d into a dmg named volname '''
        dmg = os.path.join(destdir, volname+'.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        subprocess.check_call(['hdiutil', 'create', '-srcfolder', os.path.abspath(d), 
                               '-volname', volname, '-format', format, dmg])
        if internet_enable:
           subprocess.check_call(['hdiutil', 'internet-enable', '-yes', dmg])
        return dmg
        
    @classmethod
    def qt_dependencies(cls, path):
        pipe = subprocess.Popen('otool -L '+path, shell=True, stdout=subprocess.PIPE).stdout
        deps = []
        for l in pipe.readlines():
            match = re.search(r'(.*)\(', l)
            if not match:
                continue 
            lib = match.group(1).strip()
            if lib.startswith(BuildAPP.QT_PREFIX):
                deps.append(lib)
        return deps
    
    @classmethod
    def fix_qt_dependencies(cls, path, deps):
        fp = '@executable_path/../Frameworks/'
        print 'Fixing qt dependencies for:', os.path.basename(path)
        for dep in deps:
            module = re.search(r'(Qt\w+?)\.framework', dep).group(1)            
            newpath = fp + '%s.framework/Versions/Current/%s'%(module, module)
            cmd = ' '.join(['install_name_tool', '-change', dep, newpath, path])        
            subprocess.check_call(cmd, shell=True)
        
    
    def add_qt_plugins(self):
        macos_dir = os.path.join(self.dist_dir, APPNAME + '.app', 'Contents', 'MacOS')
        for root, dirs, files in os.walk(BuildAPP.QT_PREFIX+'/plugins'):
            for name in files:
                if name.endswith('.dylib'):
                    path = os.path.join(root, name)
                    dir = os.path.basename(root)
                    dest_dir = os.path.join(macos_dir, dir)
                    if not os.path.exists(dest_dir):
                        os.mkdir(dest_dir)
                    target = os.path.join(dest_dir, name)
                    shutil.copyfile(path, target)
                    shutil.copymode(path, target)
                    deps = BuildAPP.qt_dependencies(target)
                    BuildAPP.fix_qt_dependencies(target, deps)
                                            
            
        #deps = BuildAPP.qt_dependencies(path)
            
    
    def run(self):
        py2app.run(self)
        self.add_qt_plugins()
        resource_dir = os.path.join(self.dist_dir, 
                                    APPNAME + '.app', 'Contents', 'Resources')
        frameworks_dir = os.path.join(os.path.dirname(resource_dir), 'Frameworks')
        all_scripts = scripts['console'] + scripts['gui']
        all_names   = basenames['console'] + basenames['gui']
        all_modules   = main_modules['console'] + main_modules['gui']
        all_functions = main_functions['console'] + main_functions['gui']
        print
        for name, module, function in zip(all_names, all_modules, all_functions):
            path = os.path.join(resource_dir, name)
            print 'Creating loader:', path
            f = open(path, 'w')
            f.write(BuildAPP.LOADER_TEMPLATE % dict(module=module, 
                                                        function=function))
            f.close()
            os.chmod(path, stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH|stat.S_IREAD\
                     |stat.S_IWUSR|stat.S_IROTH|stat.S_IRGRP)
            
        print
        print 'Adding clit'
        os.link(os.path.expanduser('~/clit'), os.path.join(frameworks_dir, 'clit'))
        print 
        print 'Adding unrtf'
        os.link(os.path.expanduser('~/unrtf'), os.path.join(frameworks_dir, 'unrtf'))
        print 
        print 'Adding pdftohtml'
        os.link(os.path.expanduser('~/pdftohtml'), os.path.join(frameworks_dir, 'pdftohtml'))
        print
        print 'Installing prescipt'
        sf = [os.path.basename(s) for s in all_names]
        cs = BuildAPP.CHECK_SYMLINKS_PRESCRIPT % dict(dest_path=repr('/usr/bin'),
                                                      scripts=repr(sf),
                                                      sp='%s', pp='%')
        launcher_path = os.path.join(resource_dir, '__boot__.py')
        f = open(launcher_path, 'r')
        src = f.read()
        f.close()
        src = re.sub('(_run\s*\(.*?.py.*?\))', cs+'%s'%(
'''
sys.frameworks_dir = os.path.join(os.path.dirname(os.environ['RESOURCEPATH']), 'Frameworks')
''') + r'\n\1', src)
        f = open(launcher_path, 'w')
        print >>f, 'import sys, os'
        f.write(src)
        f.close()
        print
        print 'Building disk image'
        BuildAPP.makedmg(os.path.join(self.dist_dir, APPNAME+'.app'), APPNAME+'-'+VERSION)


def main():
    auto = '--auto' in sys.argv
    if auto:
        sys.argv.remove('--auto')
    if auto and not os.path.exists('dist/auto'):
        print '%s does not exist'%os.path.abspath('dist/auto')
        return 1
    
    sys.argv[1:2] = ['py2app']
    setup(
        name = APPNAME,
        app = [scripts['gui'][0]],
        cmdclass = { 'py2app' : BuildAPP },
        options  = { 'py2app' :
                     {
                         'optimize' : 2,
                         'dist_dir' : 'build/py2app',
                         'argv_emulation' : True,
                         'iconfile' : 'icons/library.icns',
                         'frameworks': ['libusb.dylib', 'libunrar.dylib'],
                         'includes' : ['sip', 'pkg_resources', 'PyQt4.QtSvg', 
                                       'mechanize', 'ClientForm', 'usbobserver'],
                         'packages' : ['PIL', 'Authorization', 'rtf2xml', 'lxml'],
                         'excludes' : ['pydoc'],
                         'plist'    : { 'CFBundleGetInfoString' : '''libprs500, an E-book management application.'''
                                        ''' Visit http://libprs500.kovidgoyal.net for details.''',
                                        'CFBundleIdentifier':'net.kovidgoyal.librs500',
                                        'CFBundleShortVersionString':VERSION,
                                        'CFBundleVersion':APPNAME + ' ' + VERSION,
                                        'LSMinimumSystemVersion':'10.4.3',
                                        'LSMultipleInstancesProhibited':'true',
                                        'NSHumanReadableCopyright':'Copyright 2006, Kovid Goyal',
                                       },
                      },
                    },
        setup_requires = ['py2app'],
        )
    if auto:
        subprocess.call(('sudo', 'shutdown', '-h', '+0'))
    return 0

if __name__ == '__main__':
    sys.exit(main())