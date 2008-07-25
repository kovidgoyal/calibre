#!/usr/bin/env python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Create an OSX installer '''

import sys, re, os, shutil, subprocess, stat, glob, zipfile
l = {}
exec open('setup.py').read() in l
VERSION = l['VERSION']
APPNAME = l['APPNAME']
scripts = l['scripts']
basenames = l['basenames']
main_functions = l['main_functions']
main_modules = l['main_modules']
from setuptools import setup
from py2app.build_app import py2app
from modulegraph.find_modules import find_modules

PYTHON = '/Library/Frameworks/Python.framework/Versions/Current/bin/python'

class BuildAPP(py2app):
    QT_PREFIX = '/Users/kovid/qt'
    LOADER_TEMPLATE = \
r'''#!/usr/bin/env python
import os, sys, glob
path = os.path.abspath(os.path.realpath(__file__))
dirpath = os.path.dirname(path)
name = os.path.basename(path)
base_dir = os.path.dirname(os.path.dirname(dirpath))
resources_dir = os.path.join(base_dir, 'Resources')
frameworks_dir = os.path.join(base_dir, 'Frameworks')
base_name = os.path.splitext(name)[0]
python = os.path.join(base_dir, 'MacOS', 'python')
loader_path = os.path.join(dirpath, base_name+'.py')
loader = open(loader_path, 'w')
site_packages = glob.glob(resources_dir+'/lib/python*/site-packages.zip')[0]
print >>loader, '#!'+python
print >>loader, 'import sys'
print >>loader, 'sys.path.remove('+repr(dirpath)+')'
print >>loader, 'sys.path.append(', repr(site_packages), ')'
print >>loader, 'sys.frozen = "macosx_app"'
print >>loader, 'sys.frameworks_dir =', repr(frameworks_dir)
print >>loader, 'import os'
print >>loader, 'from %(module)s import %(function)s'
print >>loader, '%(function)s()'
loader.close()
os.chmod(loader_path, 0700)
os.environ['PYTHONHOME'] = resources_dir
os.environ['FC_CONFIG_DIR'] = os.path.join(resources_dir, 'fonts')
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
    omask = os.umask(022)
    os.symlink(s, l)
    os.umask(omask)
"""
    
    dest_path = %(dest_path)s
    resources_path = os.environ['RESOURCEPATH']
    scripts = %(scripts)s    
    links   = [os.path.join(dest_path, i) for i in scripts]
    scripts = [os.path.join(resources_path, 'loaders', i) for i in scripts]
    
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
            pipe = auth.executeWithPrivileges(sys.executable, name)
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
            debug=debug)
        
    @classmethod
    def makedmg(cls, d, volname, 
                destdir='dist', 
                internet_enable=True,
                format='UDBZ'):
        ''' Copy a directory d into a dmg named volname '''
        dmg = os.path.join(destdir, volname+'.dmg')
        if os.path.exists(dmg):
            os.unlink(dmg)
        subprocess.check_call(['/usr/bin/hdiutil', 'create', '-srcfolder', os.path.abspath(d), 
                               '-volname', volname, '-format', format, dmg])
        if internet_enable:
           subprocess.check_call(['/usr/bin/hdiutil', 'internet-enable', '-yes', dmg])
        return dmg
        
    @classmethod
    def qt_dependencies(cls, path):
        pipe = subprocess.Popen('/usr/bin/otool -L '+path, shell=True, stdout=subprocess.PIPE).stdout
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
            match = re.search(r'(Qt\w+?)\.framework', dep)
            if not match:
                match = re.search(r'(phonon)\.framework', dep)
                if not match:
                    print dep
                    raise Exception('Unknown Qt dependency')
            module = match.group(1)            
            newpath = fp + '%s.framework/Versions/Current/%s'%(module, module)
            cmd = ' '.join(['/usr/bin/install_name_tool', '-change', dep, newpath, path])        
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
    
    def fix_python_dependencies(self, files):
        for f in files:
            subprocess.check_call(['/usr/bin/install_name_tool', '-change', '/Library/Frameworks/Python.framework/Versions/2.5/Python', '@executable_path/../Frameworks/Python.framework/Versions/2.5/Python', f])
            
    def fix_misc_dependencies(self, files):
        for path in files:
            frameworks_dir = os.path.join(self.dist_dir, APPNAME + '.app', 'Contents', 'Frameworks')
            pipe = subprocess.Popen('/usr/bin/otool -L '+path, shell=True, stdout=subprocess.PIPE).stdout
            for l in pipe.readlines():
                match = re.search(r'\s+(.*?)\s+\(', l)
                if match:
                    dep = match.group(1)
                    name = os.path.basename(dep)
                    if not name:
                        name = dep
                    bundle = os.path.join(frameworks_dir, name)
                    if os.path.exists(bundle):
                        subprocess.check_call(['/usr/bin/install_name_tool', '-change', dep,
                                '@executable_path/../Frameworks/'+name, path])
                    
    
    def add_plugins(self):
        self.add_qt_plugins()
        frameworks_dir = os.path.join(self.dist_dir, APPNAME + '.app', 'Contents', 'Frameworks')
        plugins_dir = os.path.join(frameworks_dir, 'plugins')
        if not os.path.exists(plugins_dir):
            os.mkdir(plugins_dir)
        
        maps = {}
        for f in glob.glob('src/calibre/plugins/*'):
            tgt = plugins_dir
            if f.endswith('.dylib'):
                tgt = frameworks_dir
            maps[f] = os.path.join(tgt, os.path.basename(f))
        deps = []
        for src, dst in maps.items():
            shutil.copyfile(src, dst)
            self.fix_qt_dependencies(dst, self.qt_dependencies(dst))
            deps.append(dst)
        self.fix_python_dependencies(deps)
        self.fix_misc_dependencies(deps)
        
    
    def run(self):
        py2app.run(self)
        resource_dir = os.path.join(self.dist_dir, 
                                    APPNAME + '.app', 'Contents', 'Resources')
        frameworks_dir = os.path.join(os.path.dirname(resource_dir), 'Frameworks')
        all_scripts = scripts['console'] + scripts['gui']
        all_names   = basenames['console'] + basenames['gui']
        all_modules   = main_modules['console'] + main_modules['gui']
        all_functions = main_functions['console'] + main_functions['gui']
        print
        loader_path = os.path.join(resource_dir, 'loaders')
        if not os.path.exists(loader_path):
            os.mkdir(loader_path)
        for name, module, function in zip(all_names, all_modules, all_functions):
            path = os.path.join(loader_path, name)
            print 'Creating loader:', path
            f = open(path, 'w')
            f.write(BuildAPP.LOADER_TEMPLATE % dict(module=module, 
                                                        function=function))
            f.close()
            os.chmod(path, stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH|stat.S_IREAD\
                     |stat.S_IWUSR|stat.S_IROTH|stat.S_IRGRP)
        self.add_plugins()
        
            
        print
        print 'Adding clit'
        os.link(os.path.expanduser('~/clit'), os.path.join(frameworks_dir, 'clit'))
        print 
        print 'Adding unrtf'
        os.link(os.path.expanduser('~/unrtf'), os.path.join(frameworks_dir, 'unrtf'))
        print 
        print 'Adding pdftohtml'
        os.link(os.path.expanduser('~/pdftohtml'), os.path.join(frameworks_dir, 'pdftohtml'))
        print 'Adding plugins'
        module_dir = os.path.join(resource_dir, 'lib', 'python2.5', 'lib-dynload')
        print 'Adding fontconfig'
        for f in glob.glob(os.path.expanduser('~/fontconfig-bundled/*')):
            os.link(f, os.path.join(frameworks_dir, os.path.basename(f)))
        dst = os.path.join(resource_dir, 'fonts')
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree('/usr/local/etc/fonts', dst, symlinks=False)
        
        print
        print 'Adding IPython'
        dst = os.path.join(resource_dir, 'lib', 'python2.5', 'IPython')
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(os.path.expanduser('~/build/ipython/IPython'), dst)
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
        print 'Adding main scripts to site-packages'
        f = zipfile.ZipFile(os.path.join(self.dist_dir, APPNAME+'.app', 'Contents', 'Resources', 'lib', 'python2.5', 'site-packages.zip'), 'a', zipfile.ZIP_DEFLATED)
        for script in scripts['gui']+scripts['console']:
            f.write(script, script.partition('/')[-1])
        f.close()
        print
        print 'Building disk image'
        BuildAPP.makedmg(os.path.join(self.dist_dir, APPNAME+'.app'), APPNAME+'-'+VERSION)

def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
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
                         'includes' : ['sip', 'pkg_resources', 'PyQt4.QtXml',
                                       'PyQt4.QtSvg', 'PyQt4.QtWebKit',
                                       'mechanize', 'ClientForm', 'usbobserver',
                                       'genshi', 'calibre.web.feeds.recipes.*',
                                       'calibre.ebooks.lrf.any.*', 'calibre.ebooks.lrf.feeds.*',
                                       'keyword', 'codeop', 'pydoc', 'readline'],
                         'packages' : ['PIL', 'Authorization', 'rtf2xml', 'lxml'],
                         'excludes' : ['IPython'],
                         'plist'    : { 'CFBundleGetInfoString' : '''calibre, an E-book management application.'''
                                        ''' Visit http://calibre.kovidgoyal.net for details.''',
                                        'CFBundleIdentifier':'net.kovidgoyal.calibre',
                                        'CFBundleShortVersionString':VERSION,
                                        'CFBundleVersion':APPNAME + ' ' + VERSION,
                                        'LSMinimumSystemVersion':'10.4.3',
                                        'LSMultipleInstancesProhibited':'true',
                                        'NSHumanReadableCopyright':'Copyright 2008, Kovid Goyal',
                                        'LSEnvironment':{
                                                         'FC_CONFIG_DIR':'@executable_path/../Resources/fonts',
                                                         }
                                       },
                      },
                    },
        setup_requires = ['py2app'],
        )
    return 0

if __name__ == '__main__':
    sys.exit(main())
