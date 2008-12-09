#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Build PyQt extensions. Integrates with distutils (but uses the PyQt build system).
'''
from distutils.core import Extension as _Extension
from distutils.command.build_ext import build_ext as _build_ext
from distutils.dep_util import newer_group
from distutils import log

import sipconfig, os, sys, string, glob, shutil
from PyQt4 import pyqtconfig
iswindows = 'win32' in sys.platform
QMAKE = os.path.expanduser('~/qt/bin/qmake') if 'darwin' in sys.platform else'qmake'
WINDOWS_PYTHON = ['C:/Python26/libs']
OSX_SDK = '/Developer/SDKs/MacOSX10.4u.sdk'

def replace_suffix(path, new_suffix):
    return os.path.splitext(path)[0] + new_suffix

class Extension(_Extension):
    pass

if iswindows:
    from distutils import msvc9compiler
    msvc = msvc9compiler.MSVCCompiler()
    msvc.initialize()
    nmake = msvc.find_exe('nmake.exe')
    rc = msvc.find_exe('rc.exe')


class PyQtExtension(Extension):

    def __init__(self, name, sources, sip_sources, **kw):
        '''
        :param sources: Qt .cpp and .h files needed for this extension
        :param sip_sources: List of .sip files this extension depends on. The
                            first .sip file will be used toactually build the extension.
        '''
        self.module_makefile = pyqtconfig.QtGuiModuleMakefile
        self.sip_sources = map(lambda x: x.replace('/', os.sep), sip_sources)
        Extension.__init__(self, name, sources, **kw)


class build_ext(_build_ext):

    def make(self, makefile):
        make = nmake if iswindows else 'make'
        self.spawn([make, '-f', makefile])

    def build_qt_objects(self, ext, bdir):
        if not iswindows:
            bdir = os.path.join(bdir, 'qt')
        if not os.path.exists(bdir):
            os.makedirs(bdir)
        cwd = os.getcwd()
        sources = map(os.path.abspath, ext.sources)
        os.chdir(bdir)
        try:
            headers = set([f for f in sources if f.endswith('.h')])
            sources = set(sources) - headers
            name = ext.name.rpartition('.')[-1]
            pro = '''\
TARGET   = %s
TEMPLATE = lib
HEADERS  = %s
SOURCES  = %s
VERSION  = 1.0.0
CONFIG   += x86 ppc
'''%(name, ' '.join(headers), ' '.join(sources))
            open(name+'.pro', 'wb').write(pro)
            self.spawn([QMAKE, '-o', 'Makefile.qt', name+'.pro'])
            self.make('Makefile.qt')
            pat = 'release\\*.obj' if iswindows else '*.o'
            return map(os.path.abspath, glob.glob(pat))
        finally:
            os.chdir(cwd)

    def build_sbf(self, sip, sbf, bdir):
        print '\tBuilding spf...'
        sip_bin = self.sipcfg.sip_bin
        self.spawn([sip_bin,
                    "-c", bdir,
                    "-b", sbf,
                    '-I', self.pyqtcfg.pyqt_sip_dir,
                    ] + self.pyqtcfg.pyqt_sip_flags.split()+
                    [sip])

    def build_pyqt(self, bdir, sbf, ext, qtobjs, headers):
        makefile = ext.module_makefile(configuration=self.pyqtcfg,
                                       build_file=sbf, dir=bdir,
                                       makefile='Makefile.pyqt',
                                       universal=OSX_SDK, qt=1)
        if 'win32' in sys.platform:
            makefile.extra_lib_dirs += WINDOWS_PYTHON
        makefile.extra_include_dirs = list(set(map(os.path.dirname, headers)))
        makefile.extra_lflags += qtobjs
        makefile.generate()
        cwd = os.getcwd()
        os.chdir(bdir)
        try:
            self.make('Makefile.pyqt')
        finally:
            os.chdir(cwd)



    def build_extension(self, ext):
        self.inplace = True # Causes extensions to be built in the source tree
        
        fullname = self.get_ext_fullname(ext.name)
        if self.inplace:
            # ignore build-lib -- put the compiled extension into
            # the source tree along with pure Python modules

            modpath = string.split(fullname, '.')
            package = string.join(modpath[0:-1], '.')
            base = modpath[-1]

            build_py = self.get_finalized_command('build_py')
            package_dir = build_py.get_package_dir(package)
            ext_filename = os.path.join(package_dir,
                                        self.get_ext_filename(base))
        else:
            ext_filename = os.path.join(self.build_lib,
                                        self.get_ext_filename(fullname))
        bdir = os.path.abspath(os.path.join(self.build_temp, fullname))    
        if not os.path.exists(bdir):
            os.makedirs(bdir)
            
        if not isinstance(ext, PyQtExtension):
            if not iswindows:
                return _build_ext.build_extension(self, ext)
            
            c_sources = [f for f in ext.sources if os.path.splitext(f)[1].lower() in ('.c', '.cpp', '.cxx')]
            compile_args = '/c /nologo /Ox /MD /W3 /GX /DNDEBUG'.split()
            compile_args += ext.extra_compile_args
            self.swig_opts = ''
            inc_dirs = self.include_dirs + [x.replace('/', '\\') for x in ext.include_dirs]
            cc = [msvc.cc] + compile_args + ['-I%s'%x for x in list(set(inc_dirs))]
            objects = []
            for f in c_sources:
                o = os.path.join(bdir, os.path.basename(f)+'.obj')
                objects.append(o)
                compiler =  cc + ['/Tc'+f, '/Fo'+o]
                self.spawn(compiler)
            out = os.path.join(bdir, base+'.pyd') 
            linker = [msvc.linker] + '/DLL /nologo /INCREMENTAL:NO'.split()
            linker += ['/LIBPATH:'+x for x in self.library_dirs]
            linker += [x+'.lib' for x in ext.libraries]
            linker += ['/EXPORT:init'+base] + objects + ['/OUT:'+out]
            self.spawn(linker)
            for src in (out, out+'.manifest'):
                shutil.copyfile(src, os.path.join('src', 'calibre', 'plugins', os.path.basename(src)))
            return
                
        
        
        if not os.path.exists(bdir):
            os.makedirs(bdir)
        ext.sources2 = map(os.path.abspath, ext.sources)
        qt_dir = 'qt\\release' if iswindows else 'qt'
        objects = set(map(lambda x: os.path.join(bdir, qt_dir, replace_suffix(os.path.basename(x), '.o')),
                      [s for s in ext.sources2 if not s.endswith('.h')]))
        newer = False
        for object in objects:
            if newer_group(ext.sources2, object, missing='newer'):
                newer = True
                break
        headers = [f for f in ext.sources2 if f.endswith('.h')]
        if self.force or newer:
            log.info('building \'%s\' extension', ext.name)
            objects = self.build_qt_objects(ext, bdir)

        self.sipcfg  = sipconfig.Configuration()
        self.pyqtcfg = pyqtconfig.Configuration()
        sbf_sources = []
        for sip in ext.sip_sources:
            sipbasename = os.path.basename(sip)
            sbf = os.path.join(bdir, replace_suffix(sipbasename, ".sbf"))
            sbf_sources.append(sbf)
            if self.force or newer_group(ext.sip_sources, sbf, 'newer'):
                self.build_sbf(sip, sbf, bdir)
        generated_sources = []
        for sbf in sbf_sources:
            generated_sources += self.get_sip_output_list(sbf, bdir)

        depends = generated_sources + list(objects)
        mod = os.path.join(bdir, os.path.basename(ext_filename))

        if self.force or newer_group(depends, mod, 'newer'):
            self.build_pyqt(bdir, sbf_sources[0], ext, list(objects), headers)

        if self.force or newer_group([mod], ext_filename, 'newer'):
            if os.path.exists(ext_filename):
                os.unlink(ext_filename)
            shutil.copyfile(mod, ext_filename)
            shutil.copymode(mod, ext_filename)

    def get_sip_output_list(self, sbf, bdir):
        """
        Parse the sbf file specified to extract the name of the generated source
        files. Make them absolute assuming they reside in the temp directory.
        """
        for L in file(sbf):
            key, value = L.split("=", 1)
            if key.strip() == "sources":
                out = []
                for o in value.split():
                    out.append(os.path.join(bdir, o))
                return out

        raise RuntimeError, "cannot parse SIP-generated '%s'" % sbf

    def run_sip(self, sip_files):
        sip_bin = self.sipcfg.sip_bin
        sip_sources = [i[0] for i in sip_files]
        generated_sources = []
        for sip, sbf in sip_files:
            if not (self.force or newer_group(sip_sources, sbf, 'newer')):
                log.info(sbf + ' is up to date')
                continue
            self.spawn([sip_bin,
                    "-c", self.build_temp,
                    "-b", sbf,
                    '-I', self.pyqtcfg.pyqt_sip_dir,
                    ] + self.pyqtcfg.pyqt_sip_flags.split()+
                    [sip])
            generated_sources += self.get_sip_output_list(sbf)
        return generated_sources

