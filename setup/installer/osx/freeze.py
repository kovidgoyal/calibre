#!/usr/bin/env python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' Create an OSX installer '''

import sys, re, os, shutil, subprocess, stat, glob, zipfile, plistlib
from setup import __version__ as VERSION, __appname__ as APPNAME, SRC, Command, \
        scripts, basenames, functions as main_functions, modules as main_modules

try:
    from setuptools import setup
    setup
except:
    class setup:
        pass

try:
    from py2app.build_app import py2app
    from modulegraph.find_modules import find_modules
    py2app
except ImportError:
    py2app = object

PYTHON = '/Library/Frameworks/Python.framework/Versions/Current/bin/python'

info = warn = None

class OSX32_Freeze(Command):

    description = 'Freeze OSX calibre installation'

    def run(self, opts):
        global info, warn
        info, warn = self.info, self.warn
        main()


class BuildAPP(py2app):
    QT_PREFIX = '/Volumes/sw/qt'
    LOADER_TEMPLATE = \
r'''#!/usr/bin/env python
import os, sys, glob
path = os.path.abspath(os.path.realpath(__file__))
dirpath = os.path.dirname(path)
name = os.path.basename(path)
base_dir = os.path.dirname(os.path.dirname(dirpath))
resources_dir = os.path.join(base_dir, 'Resources')
frameworks_dir = os.path.join(base_dir, 'Frameworks')
extensions_dir = os.path.join(frameworks_dir, 'plugins')
r_dir = os.path.join(resources_dir, 'resources')
base_name = os.path.splitext(name)[0]
python = os.path.join(base_dir, 'MacOS', 'python')
qt_plugins = os.path.join(os.path.realpath(base_dir), 'MacOS')
loader_path = os.path.join(dirpath, base_name+'.py')
loader = open(loader_path, 'w')
site_packages = glob.glob(resources_dir+'/lib/python*/site-packages.zip')[0]
devf = os.environ.get('CALIBRE_DEVELOP_FROM', None)
do_devf = devf and os.path.exists(devf)
if do_devf:
    devf = os.path.abspath(devf)
print >>loader, 'import sys'
print >>loader, 'sys.argv[0] =', repr(os.path.basename(path))
print >>loader, 'if', repr(dirpath), 'in sys.path: sys.path.remove(', repr(dirpath), ')'
print >>loader, 'sys.path.append(', repr(site_packages), ')'
if do_devf:
    print >>loader, 'sys.path.insert(0, '+repr(devf)+')'
print >>loader, 'sys.frozen = "macosx_app"'
print >>loader, 'sys.frameworks_dir =', repr(frameworks_dir)
print >>loader, 'sys.extensions_location =', repr(extensions_dir)
print >>loader, 'sys.resources_location =', repr(r_dir)
print >>loader, 'import os'
print >>loader, 'from %(module)s import %(function)s'
print >>loader, '%(function)s()'
loader.close()
os.chmod(loader_path, 0700)
os.environ['PYTHONHOME']        = resources_dir
os.environ['FONTCONFIG_PATH']   = os.path.join(resources_dir, 'fonts')
os.environ['MAGICK_HOME']       = os.path.join(frameworks_dir, 'ImageMagick')
os.environ['DYLD_LIBRARY_PATH'] = os.path.join(frameworks_dir, 'ImageMagick', 'lib')
os.environ['QT_PLUGIN_PATH']    = qt_plugins
args = [path, loader_path] + sys.argv[1:]
os.execv(python, args)
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
        if not os.path.exists(destdir):
            os.makedirs(destdir)
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
        info('Fixing qt dependencies for:', os.path.basename(path))
        for dep in deps:
            match = re.search(r'(Qt\w+?)\.framework', dep)
            if not match:
                match = re.search(r'(phonon)\.framework', dep)
                if not match:
                    warn(dep)
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
            subprocess.check_call(['/usr/bin/install_name_tool', '-change', '/Library/Frameworks/Python.framework/Versions/2.6/Python', '@executable_path/../Frameworks/Python.framework/Versions/2.6/Python', f])

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

    def fix_image_magick_deps(self, root):
        modules = []
        frameworks_dir = os.path.dirname(root)
        for x in os.walk(root):
            for f in x[-1]:
                if f.endswith('.so'):
                    modules.append(os.path.join(x[0], f))
        for x in os.walk(os.path.join(frameworks_dir, 'plugins')):
            for f in x[-1]:
                if f.endswith('.so'):
                    modules.append(os.path.join(x[0], f))

        deps = {}
        for x in ('Core.1', 'Wand.1'):
            modules.append(os.path.join(root, 'lib', 'libMagick%s.dylib'%x))
            x = modules[-1]
            deps[os.path.join('/Users/kovid/ImageMagick/lib',
                os.path.basename(x))] = '@executable_path/../Frameworks/ImageMagick/lib/'+os.path.basename(x)
            subprocess.check_call(['install_name_tool', '-id',
            '@executable_path/../Frameworks/ImageMagick/lib/'+os.path.basename(x),
            x])
        for x in ('/usr/local/lib/libfreetype.6.dylib',
                    '/Volumes/sw/lib/libwmflite-0.2.7.dylib'):
            deps[x] = '@executable_path/../Frameworks/'+ os.path.basename(x)

        for x in modules:
            print 'Fixing deps in', x
            for f, t in deps.items():
                subprocess.check_call(['install_name_tool', '-change', f, t, x])


    def run(self):
        py2app.run(self)
        resource_dir = os.path.join(self.dist_dir,
                                    APPNAME + '.app', 'Contents', 'Resources')
        frameworks_dir = os.path.join(os.path.dirname(resource_dir), 'Frameworks')
        all_scripts = scripts['console'] + scripts['gui']
        all_names   = basenames['console'] + basenames['gui']
        all_modules   = main_modules['console'] + main_modules['gui']
        all_functions = main_functions['console'] + main_functions['gui']

        info('\nAdding resources')
        dest = os.path.join(resource_dir, 'resources')
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.join(os.path.dirname(SRC), 'resources'), dest)

        info('\nAdding PoDoFo')
        pdf = glob.glob(os.path.expanduser('/Volumes/sw/podofo/libpodofo*.dylib'))[0]
        shutil.copyfile(pdf, os.path.join(frameworks_dir, os.path.basename(pdf)))

        info('\nAdding poppler')
        popps = []
        for x in ('bin/pdftohtml', 'lib/libpoppler.5.dylib'):
            dest = os.path.join(frameworks_dir, os.path.basename(x))
            popps.append(dest)
            shutil.copy2(os.path.join('/Volumes/sw', x), dest)
        subprocess.check_call(['install_name_tool', '-change',
            '/usr/local/lib/libfontconfig.1.dylib',
            '@executable_path/../Frameworks/libfontconfig.1.dylib',
            os.path.join(frameworks_dir, 'pdftohtml')])
        x ='libpng12.0.dylib'
        shutil.copy2('/usr/local/lib/'+x, frameworks_dir)
        subprocess.check_call(['install_name_tool', '-id',
            '@executable_path/../Frameworks/'+x, os.path.join(frameworks_dir, x)])
        self.fix_misc_dependencies(popps)
        subprocess.check_call(['install_name_tool', '-change',
        '/usr/local/lib/libfontconfig.1.dylib',
        '@executable_path/../Frameworks/libfontconfig.1.dylib', popps[1]])
        subprocess.check_call(['install_name_tool', '-id',
        '@executable_path/../Frameworks/'+os.path.basename(popps[1]), popps[1]])

        loader_path = os.path.join(resource_dir, 'loaders')
        if not os.path.exists(loader_path):
            os.mkdir(loader_path)
        for name, module, function in zip(all_names, all_modules, all_functions):
            path = os.path.join(loader_path, name)
            info('Creating loader:', path)
            f = open(path, 'w')
            f.write(BuildAPP.LOADER_TEMPLATE % dict(module=module,
                                                        function=function))
            f.close()
            os.chmod(path, stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH|stat.S_IREAD\
                     |stat.S_IWUSR|stat.S_IROTH|stat.S_IRGRP)


        info('Adding fontconfig')
        for f in glob.glob(os.path.expanduser('~/fontconfig-bundled/*')):
            dest = os.path.join(frameworks_dir, os.path.basename(f))
            if os.path.exists(dest):
                os.remove(dest)
            shutil.copyfile(f, dest)
        dst = os.path.join(resource_dir, 'fonts')
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree('/usr/local/etc/fonts', dst, symlinks=False)

        self.add_plugins()


        info('Adding IPython')
        dst = os.path.join(resource_dir, 'lib', 'python2.6', 'IPython')
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(os.path.expanduser('~/build/ipython/IPython'), dst)


        info('Adding ImageMagick')
        libwmf = '/Volumes/sw/lib/libwmflite-0.2.7.dylib'
        dest = os.path.join(frameworks_dir, os.path.basename(libwmf))
        shutil.copy2(libwmf, frameworks_dir)
        nid = '@executable_path/../Frameworks/'+os.path.basename(dest)
        subprocess.check_call(['install_name_tool', '-id', nid, dest])
        dest = os.path.join(frameworks_dir, 'ImageMagick')
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.expanduser('~/ImageMagick'), dest, True)
        shutil.rmtree(os.path.join(dest, 'include'))
        shutil.rmtree(os.path.join(dest, 'share', 'doc'))
        shutil.rmtree(os.path.join(dest, 'share', 'man'))
        shutil.copyfile('/usr/local/lib/libpng12.0.dylib', os.path.join(dest, 'lib', 'libpng12.0.dylib'))
        self.fix_image_magick_deps(dest)


        info('Installing prescipt')
        sf = [os.path.basename(s) for s in all_names]
        launcher_path = os.path.join(resource_dir, '__boot__.py')
        f = open(launcher_path, 'r')
        src = f.read()
        f.close()
        src = src.replace('import Image', 'from PIL import Image')
        src = re.sub('(_run\s*\(.*?.py.*?\))', '%s'%(
'''
sys.frameworks_dir = os.path.join(os.path.dirname(os.environ['RESOURCEPATH']), 'Frameworks')
sys.resources_location = os.path.join(os.environ['RESOURCEPATH'], 'resources')
sys.extensions_location = os.path.join(sys.frameworks_dir, 'plugins')
devf = os.environ.get('CALIBRE_DEVELOP_FROM', None)
do_devf = devf and os.path.exists(devf)
if do_devf:
    devf = os.path.abspath(devf)
    sys.path.insert(0, devf)
''') + r'\n\1', src)
        f = open(launcher_path, 'w')
        print >>f, 'import sys, os'
        f.write(src)
        f.close()

        info('\nAdding main scripts to site-packages')
        f = zipfile.ZipFile(os.path.join(self.dist_dir, APPNAME+'.app', 'Contents', 'Resources', 'lib', 'python'+sys.version[:3], 'site-packages.zip'), 'a', zipfile.ZIP_DEFLATED)
        for script in scripts['gui']+scripts['console']:
            f.write(script, script.partition('/')[-1])
        f.close()

        info('\nCreating console.app')
        contents_dir = os.path.dirname(resource_dir)
        cc_dir = os.path.join(contents_dir, 'console.app', 'Contents')
        os.makedirs(cc_dir)
        for x in os.listdir(contents_dir):
            if x == 'console.app':
                continue
            if x == 'Info.plist':
                plist = plistlib.readPlist(os.path.join(contents_dir, x))
                plist['LSUIElement'] = '1'
                plistlib.writePlist(plist, os.path.join(cc_dir, x))
            else:
                os.symlink(os.path.join('../..', x),
                           os.path.join(cc_dir, x))

        info('\nBuilding disk image')
        BuildAPP.makedmg(os.path.join(self.dist_dir, APPNAME+'.app'), APPNAME+'-'+VERSION)

def main():
    sys.argv[1:2] = ['py2app']
    d = os.path.dirname
    icon = os.path.abspath('icons/library.icns')
    if not os.access(icon, os.R_OK):
        raise Exception('No icon at '+icon)
    setup(
        name = APPNAME,
        app = [scripts['gui'][0]],
        cmdclass = { 'py2app' : BuildAPP },
        options  = { 'py2app' :
                     {
                         'optimize' : 2,
                         'dist_dir' : 'build/py2app',
                         'argv_emulation' : True,
                         'iconfile' : icon,
                         'frameworks': ['libusb.dylib'],
                         'includes' : ['sip', 'pkg_resources', 'PyQt4.QtXml',
                                       'PyQt4.QtSvg', 'PyQt4.QtWebKit', 'commands',
                                       'mechanize', 'ClientForm', 'usbobserver',
                                       'genshi', 'calibre.web.feeds.recipes.*',
                                       'calibre.gui2.convert.*',
                                       'PyQt4.QtNetwork',
                                       'keyword', 'codeop', 'pydoc', 'readline',
                                       'BeautifulSoup',
                                       'dateutil', 'email.iterators',
                                       'email.generator', 'sqlite3.dump',
                                       'calibre.ebooks.metadata.amazon',
                                       ],
                         'packages' : ['PIL', 'Authorization', 'lxml', 'dns'],
                         'excludes' : ['IPython', 'PyQt4.uic.port_v3.proxy_base'],
                         'plist'    : { 'CFBundleGetInfoString' : '''calibre, an E-book management application.'''
                                        ''' Visit http://calibre-ebook.com for details.''',
                                        'CFBundleIdentifier':'net.kovidgoyal.calibre',
                                        'CFBundleShortVersionString':VERSION,
                                        'CFBundleVersion':APPNAME + ' ' + VERSION,
                                        'LSMinimumSystemVersion':'10.4.3',
                                        'LSMultipleInstancesProhibited':'true',
                                        'NSHumanReadableCopyright':'Copyright 2008, Kovid Goyal',
                                        'LSEnvironment':{
                                                         'FC_CONFIG_DIR':'@executable_path/../Resources/fonts',
                                                         'MAGICK_HOME':'@executable_path/../Frameworks/ImageMagick',
                                                         'DYLD_LIBRARY_PATH':'@executable_path/../Frameworks/ImageMagick/lib',
                                                         }
                                       },
                      },
                    },
        setup_requires = ['py2app'],
        )
    return 0

