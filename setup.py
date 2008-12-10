from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re, os, shutil, cStringIO, tempfile, subprocess, time
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
    from distutils.command.build import build as _build
    from distutils.core import Command as _Command
    from pyqtdistutils import PyQtExtension, build_ext, Extension
    import subprocess, glob
    
    def newer(targets, sources):
        '''
        Return True is sources is newer that targets or if targets
        does not exist. 
        '''
        for f in targets:
            if not os.path.exists(f):
                return True
        ttimes = map(lambda x: os.stat(x).st_mtime, targets)
        stimes = map(lambda x: os.stat(x).st_mtime, sources)
        newest_source, oldest_target = max(stimes), min(ttimes)
        return newest_source > oldest_target
    
    class Command(_Command):
        user_options = []
        def initialize_options(self): pass
        def finalize_options(self): pass
    
    class sdist(Command):
        
        description = "create a source distribution using bzr"
        
        def run(self):
            name = 'dist/calibre-%s.tar.gz'%VERSION
            subprocess.check_call(('bzr export '+name).split())
            self.distribution.dist_files.append(('sdist', '', name))
    
    class pot(Command):
        description = '''Create the .pot template for all translatable strings'''
        
        PATH = os.path.join('src', APPNAME, 'translations')
        
        def source_files(self):
            ans = []
            for root, dirs, files in os.walk(os.path.dirname(self.PATH)):
                for name in files:
                    if name.endswith('.py'):
                        ans.append(os.path.abspath(os.path.join(root, name)))
            return ans

        
        def run(self):
            sys.path.insert(0, os.path.abspath(self.PATH))
            try:
                from pygettext import main as pygettext
                files = self.source_files()
                buf = cStringIO.StringIO()
                print 'Creating translations template'
                tempdir = tempfile.mkdtemp()
                pygettext(buf, ['-p', tempdir]+files)
                src = buf.getvalue()
                pot = os.path.join(tempdir, 'calibre.pot')
                f = open(pot, 'wb')
                f.write(src)
                f.close()
                print 'Translations template:', pot
                return pot
            finally:
                sys.path.remove(os.path.abspath(self.PATH))
            
    class manual(Command):
        description='''Build the User Manual '''

        def run(self):
            cwd = os.path.abspath(os.getcwd())
            os.chdir(os.path.join('src', 'calibre', 'manual'))
            try:
                for d in ('.build', 'cli'):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    os.makedirs(d)
                if not os.path.exists('.build'+os.sep+'html'):
                    os.makedirs('.build'+os.sep+'html')
                subprocess.check_call(['sphinx-build', '-b', 'custom', '-d', 
                                       '.build/doctrees', '.', '.build/html'])
            finally:
                os.chdir(cwd)
            
        @classmethod
        def clean(cls):
            path = os.path.join('src', 'calibre', 'manual', '.build')
            if os.path.exists(path):
                shutil.rmtree(path)
            
    class resources(Command):
        description='''Compile various resource files used in calibre. '''
        
        RESOURCES = dict(
            opf_template    = 'ebooks/metadata/opf.xml',
            ncx_template    = 'ebooks/metadata/ncx.xml',
            fb2_xsl         = 'ebooks/lrf/fb2/fb2.xsl',
            metadata_sqlite = 'library/metadata_sqlite.sql',
            jquery          = 'gui2/viewer/jquery.js',
            jquery_scrollTo = 'gui2/viewer/jquery_scrollTo.js',
        )
        
        DEST = os.path.join('src', APPNAME, 'resources.py')
        
        def get_qt_translations(self):
            data = {}
            translations_found = False
            for TPATH in ('/usr/share/qt4/translations', '/usr/lib/qt4/translations'):
                if os.path.exists(TPATH):
                     files = glob.glob(TPATH + '/qt_??.qm')
                     for f in files:
                         key = os.path.basename(f).partition('.')[0]
                         data[key] = f
                     translations_found = True
                     break
            if not translations_found:
                print 'WARNING: Could not find Qt transations'
            return data
        
        def get_static_resources(self):
            sdir = os.path.join('src', 'calibre', 'library', 'static')
            resources, max = {}, 0
            for f in os.listdir(sdir):
                resources[f] = open(os.path.join(sdir, f), 'rb').read()
                mtime = os.stat(os.path.join(sdir, f)).st_mtime
                max = mtime if mtime > max else max
            return resources, max
        
        def get_recipes(self):
            sdir = os.path.join('src', 'calibre', 'web', 'feeds', 'recipes')
            resources, max = {}, 0
            for f in os.listdir(sdir):
                if f.endswith('.py') and f != '__init__.py':
                    resources[f.replace('.py', '')] = open(os.path.join(sdir, f), 'rb').read()
                    mtime = os.stat(os.path.join(sdir, f)).st_mtime
                    max = mtime if mtime > max else max
            return resources, max
        
        def run(self):
            data, dest, RESOURCES = {}, self.DEST, self.RESOURCES
            for key in RESOURCES:
                path = RESOURCES[key]
                if not os.path.isabs(path):
                    RESOURCES[key] = os.path.join('src', APPNAME, path)
            translations = self.get_qt_translations()
            RESOURCES.update(translations)
            static, smax = self.get_static_resources()
            recipes, rmax = self.get_recipes()
            amax = max(rmax, smax)
            if newer([dest], RESOURCES.values()) or os.stat(dest).st_mtime < amax:
                print 'Compiling resources...'
                with open(dest, 'wb') as f:
                    for key in RESOURCES:
                        data = open(RESOURCES[key], 'rb').read()
                        f.write(key + ' = ' + repr(data)+'\n\n')
                    f.write('server_resources = %s\n\n'%repr(static))
                    f.write('recipes = %s\n\n'%repr(recipes))
                    f.write('build_time = "%s"\n\n'%time.strftime('%d %m %Y %H%M%S'))
            else:
                print 'Resources are up to date'
        
        @classmethod
        def clean(cls):
            path = cls.DEST
            for path in glob.glob(path+'*'):
                if os.path.exists(path):
                    os.remove(path)
    
    class translations(Command):
        description='''Compile the translations'''
        PATH = os.path.join('src', APPNAME, 'translations')
        DEST = os.path.join(PATH, 'compiled.py')
        
        def run(self):
            sys.path.insert(0, os.path.abspath(self.PATH))
            try:
                files = glob.glob(os.path.join(self.PATH, '*.po'))
                if newer([self.DEST], files):
                    from msgfmt import main as msgfmt
                    translations = {}
                    print 'Compiling translations...'
                    for po in files:
                        lang = os.path.basename(po).partition('.')[0]
                        buf = cStringIO.StringIO()
                        print 'Compiling', lang
                        msgfmt(buf, [po])
                        translations[lang] = buf.getvalue()
                    open(self.DEST, 'wb').write('translations = '+repr(translations))
                else:
                    print 'Translations up to date'
            finally:
                sys.path.remove(os.path.abspath(self.PATH))
        
                
        @classmethod
        def clean(cls):
            path = cls.DEST
            if os.path.exists(path):
                os.remove(path)
            
    
    class gui(Command):
        description='''Compile all GUI forms and images'''
        PATH  = os.path.join('src', APPNAME, 'gui2')
        IMAGES_DEST = os.path.join(PATH, 'images_rc.py')
        
        @classmethod
        def find_forms(cls):
            forms = []
            for root, dirs, files in os.walk(cls.PATH):
                for name in files:
                    if name.endswith('.ui'):
                        forms.append(os.path.abspath(os.path.join(root, name)))
                
            return forms
        
        @classmethod
        def form_to_compiled_form(cls, form):
            return form.rpartition('.')[0]+'_ui.py'
        
        def run(self):
            self.build_forms()
            self.build_images()
        
        def build_images(self):
            cwd, images = os.getcwd(), os.path.basename(self.IMAGES_DEST)
            try:
                os.chdir(self.PATH)
                sources, files = [], []
                for root, dirs, files in os.walk('images'):
                    for name in files:
                        sources.append(os.path.join(root, name))
                if newer([images], sources):
                    print 'Compiling images...'
                    for s in sources:
                        alias = ' alias="library"' if s.endswith('images'+os.sep+'library.png') else ''
                        files.append('<file%s>%s</file>'%(alias, s))
                    manifest = '<RCC>\n<qresource prefix="/">\n%s\n</qresource>\n</RCC>'%'\n'.join(files)
                    with open('images.qrc', 'wb') as f:
                        f.write(manifest)
                    subprocess.check_call(['pyrcc4', '-o', images, 'images.qrc'])
                else:
                    print 'Images are up to date'
            finally:
                os.chdir(cwd)
            
        
        def build_forms(self):
            from PyQt4.uic import compileUi
            forms = self.find_forms()
            for form in forms:
                compiled_form = self.form_to_compiled_form(form) 
                if not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
                    print 'Compiling form', form
                    buf = cStringIO.StringIO()
                    compileUi(form, buf)
                    dat = buf.getvalue()
                    dat = dat.replace('__appname__', APPNAME)
                    dat = dat.replace('import images_rc', 'from calibre.gui2 import images_rc')
                    dat = dat.replace('from library import', 'from calibre.gui2.library import')
                    dat = dat.replace('from widgets import', 'from calibre.gui2.widgets import')
                    dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)', re.DOTALL).sub(r'_("\1")', dat)
                    
                    # Workaround bug in Qt 4.4 on Windows
                    if form.endswith('dialogs%sconfig.ui'%os.sep) or form.endswith('dialogs%slrf_single.ui'%os.sep):
                        print 'Implementing Workaround for buggy pyuic in form', form
                        dat = re.sub(r'= QtGui\.QTextEdit\(self\..*?\)', '= QtGui.QTextEdit()', dat) 
                        dat = re.sub(r'= QtGui\.QListWidget\(self\..*?\)', '= QtGui.QListWidget()', dat)
                    
                    if form.endswith('viewer%smain.ui'%os.sep):
                        print 'Promoting WebView'
                        dat = dat.replace('self.view = QtWebKit.QWebView(', 'self.view = DocumentView(')
                        dat += '\n\nfrom calibre.gui2.viewer.documentview import DocumentView'
                    
                    open(compiled_form, 'wb').write(dat)

                
        @classmethod
        def clean(cls):
            forms = cls.find_forms()
            for form in forms:
                c = cls.form_to_compiled_form(form)
                if os.path.exists(c):
                    os.remove(c)
            images = cls.IMAGES_DEST
            if os.path.exists(images):
                os.remove(images)
    
    class clean(Command):
        description='''Delete all computer generated files in the source tree'''
        
        def run(self):
            print 'Cleaning...'
            manual.clean()
            gui.clean()
            translations.clean()
            resources.clean()
            
            for f in glob.glob(os.path.join('src', 'calibre', 'plugins', '*')):
                os.remove(f)
            for root, dirs, files in os.walk('.'):
                for name in files:
                    if name.endswith('~') or \
                       name.endswith('.pyc') or \
                       name.endswith('.pyo'):
                        os.remove(os.path.join(root, name))
                        
            for dir in 'build', 'dist':
                for f in os.listdir(dir):
                    if os.path.isdir(dir + os.sep + f):
                        shutil.rmtree(dir + os.sep + f)
                    else:
                        os.remove(dir + os.sep + f)
    
    class build(_build):
        
        sub_commands = \
                        [
                         ('resources',    lambda self : 'CALIBRE_BUILDBOT' not in os.environ.keys()),
                         ('translations', lambda self : 'CALIBRE_BUILDBOT' not in os.environ.keys()),
                         ('gui',          lambda self : 'CALIBRE_BUILDBOT' not in os.environ.keys()),
                         ] + _build.sub_commands
    
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
                include_dirs=['C:/WinDDK/6001.18001/inc/api/',
                              'C:/WinDDK/6001.18001/inc/crt/'],
                extra_compile_args=['/X']
                ))
    if isosx:
        ext_modules.append(Extension('calibre.plugins.usbobserver',
                sources=['src/calibre/devices/usbobserver/usbobserver.c'],
                extra_link_args=['-framework', 'IOKit'])
                           )
    
    setup(
          name           = APPNAME,
          packages       = find_packages('src'),
          package_dir    = { '' : 'src' },
          version        = VERSION,
          author         = 'Kovid Goyal',
          author_email   = 'kovid@kovidgoyal.net',
          url            = 'http://%s.kovidgoyal.net'%APPNAME,
          package_data   = {'calibre':['plugins/*']},
          include_package_data = True,
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
                      'pot'           : pot,
                      'manual'        : manual,
                      'resources'     : resources,
                      'translations'  : translations,
                      'gui'           : gui,
                      'clean'         : clean,
                      'sdist'         : sdist,
                      },
         )

    if 'develop' in ' '.join(sys.argv) and islinux:
        subprocess.check_call('calibre_postinstall --do-not-reload-udev-hal', shell=True)
    if 'install' in sys.argv and islinux:
        subprocess.check_call('calibre_postinstall', shell=True)

