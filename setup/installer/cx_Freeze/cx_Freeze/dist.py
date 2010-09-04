import distutils.command.bdist_rpm
import distutils.command.build
import distutils.command.install
import distutils.core
import distutils.dir_util
import distutils.dist
import distutils.util
import distutils.version
import os
import sys

import cx_Freeze

__all__ = [ "bdist_rpm", "build", "build_exe", "install", "install_exe",
            "setup" ]

class Distribution(distutils.dist.Distribution):

    def __init__(self, attrs):
        self.executables = []
        distutils.dist.Distribution.__init__(self, attrs)


class bdist_rpm(distutils.command.bdist_rpm.bdist_rpm):

    def finalize_options(self):
        distutils.command.bdist_rpm.bdist_rpm.finalize_options(self)
        self.use_rpm_opt_flags = 1

    def _make_spec_file(self):
        contents = distutils.command.bdist_rpm.bdist_rpm._make_spec_file(self)
        return [c for c in contents if c != 'BuildArch: noarch']


class build(distutils.command.build.build):
    user_options = distutils.command.build.build.user_options + [
        ('build-exe=', None, 'build directory for executables')
    ]

    def get_sub_commands(self):
        subCommands = distutils.command.build.build.get_sub_commands(self)
        if self.distribution.executables:
            subCommands.append("build_exe")
        return subCommands

    def initialize_options(self):
        distutils.command.build.build.initialize_options(self)
        self.build_exe = None

    def finalize_options(self):
        distutils.command.build.build.finalize_options(self)
        if self.build_exe is None:
            dirName = "exe.%s-%s" % \
                    (distutils.util.get_platform(), sys.version[0:3])
            self.build_exe = os.path.join(self.build_base, dirName)


class build_exe(distutils.core.Command):
    description = "build executables from Python scripts"
    user_options = [
        ('build-exe=', 'b',
         'directory for built executables'),
        ('optimize=', 'O',
         'optimization level: -O1 for "python -O", '
         '-O2 for "python -OO" and -O0 to disable [default: -O0]'),
        ('excludes=', 'e',
         'comma-separated list of modules to exclude'),
        ('includes=', 'i',
         'comma-separated list of modules to include'),
        ('packages=', 'p',
         'comma-separated list of packages to include'),
        ('replace-paths=', None,
         'comma-separated list of paths to replace in included modules'),
        ('path=', None,
         'comma-separated list of paths to search'),
        ('init-script=', 'i',
         'name of script to use during initialization'),
        ('base=', None,
         'name of base executable to use'),
        ('compressed', 'c',
         'create a compressed zipfile'),
        ('copy-dependent-files', None,
         'copy all dependent files'),
        ('create-shared-zip', None,
         'create a shared zip file containing shared modules'),
        ('append-script-to-exe', None,
         'append the script module to the exe'),
        ('include-in-shared-zip', None,
         'include the script module in the shared zip file'),
        ('icon', None,
         'include the icon along with the frozen executable(s)'),
        ('constants=', None,
         'comma-separated list of constants to include'),
        ('include-files=', 'f',
         'list of tuples of additional files to include in distribution'),
        ('bin-includes', None,
         'list of names of files to include when determining dependencies'),
        ('bin-excludes', None,
         'list of names of files to exclude when determining dependencies')
    ]
    boolean_options = ["compressed", "copy_dependent_files",
            "create_shared_zip", "append_script_to_exe",
            "include_in_shared_zip"]

    def _normalize(self, attrName):
        value = getattr(self, attrName)
        if value is None:
            normalizedValue = []
        elif isinstance(value, basestring):
            normalizedValue = value.split()
        else:
            normalizedValue = list(value)
        setattr(self, attrName, normalizedValue)

    def initialize_options(self):
        self.optimize = 0
        self.build_exe = None
        self.excludes = []
        self.includes = []
        self.packages = []
        self.replace_paths = []
        self.compressed = None
        self.copy_dependent_files = None
        self.init_script = None
        self.base = None
        self.path = None
        self.create_shared_zip = None
        self.append_script_to_exe = None
        self.include_in_shared_zip = None
        self.icon = None
        self.constants = []
        self.include_files = []
        self.bin_excludes = []
        self.bin_includes = []

    def finalize_options(self):
        self.set_undefined_options('build', ('build_exe', 'build_exe'))
        self.optimize = int(self.optimize)
        self._normalize("excludes")
        self._normalize("includes")
        self._normalize("packages")
        self._normalize("constants")

    def run(self):
        metadata = self.distribution.metadata
        constantsModule = cx_Freeze.ConstantsModule(metadata.version)
        for constant in self.constants:
            parts = constant.split("=")
            if len(parts) == 1:
                name = constant
                value = None
            else:
                name, stringValue = parts
                value = eval(stringValue)
            constantsModule.values[name] = value
        freezer = cx_Freeze.Freezer(self.distribution.executables,
                [constantsModule], self.includes, self.excludes, self.packages,
                self.replace_paths, self.compressed, self.optimize,
                self.copy_dependent_files, self.init_script, self.base,
                self.path, self.create_shared_zip, self.append_script_to_exe,
                self.include_in_shared_zip, self.build_exe, icon = self.icon,
                includeFiles = self.include_files,
                binIncludes = self.bin_includes,
                binExcludes = self.bin_excludes)
        freezer.Freeze()


class install(distutils.command.install.install):
    user_options = distutils.command.install.install.user_options + [
            ('install-exe=', None,
             'installation directory for executables')
    ]

    def expand_dirs(self):
        distutils.command.install.install.expand_dirs(self)
        self._expand_attrs(['install_exe'])

    def get_sub_commands(self):
        subCommands = distutils.command.install.install.get_sub_commands(self)
        if self.distribution.executables:
            subCommands.append("install_exe")
        return [s for s in subCommands if s != "install_egg_info"]

    def initialize_options(self):
        distutils.command.install.install.initialize_options(self)
        self.install_exe = None

    def finalize_options(self):
        if self.prefix is None and sys.platform == "win32":
            import _winreg
            key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                    r"Software\Microsoft\Windows\CurrentVersion")
            prefix = str(_winreg.QueryValueEx(key, "ProgramFilesDir")[0])
            metadata = self.distribution.metadata
            dirName = "%s-%s" % (metadata.name, metadata.version)
            self.prefix = "%s/%s" % (prefix, dirName)
        distutils.command.install.install.finalize_options(self)
        self.convert_paths('exe')
        if self.root is not None:
            self.change_roots('exe')

    def select_scheme(self, name):
        distutils.command.install.install.select_scheme(self, name)
        if self.install_exe is None:
            if sys.platform == "win32":
                self.install_exe = '$base'
            else:
                metadata = self.distribution.metadata
                dirName = "%s-%s" % (metadata.name, metadata.version)
                self.install_exe = '$base/lib/%s' % dirName


class install_exe(distutils.core.Command):
    description = "install executables built from Python scripts"
    user_options = [
        ('install-dir=', 'd', 'directory to install executables to'),
        ('build-dir=', 'b', 'build directory (where to install from)'),
        ('force', 'f', 'force installation (overwrite existing files)'),
        ('skip-build', None, 'skip the build steps')
    ]

    def initialize_options(self):
        self.install_dir = None
        self.force = 0
        self.build_dir = None
        self.skip_build = None

    def finalize_options(self):
        self.set_undefined_options('build', ('build_exe', 'build_dir'))
        self.set_undefined_options('install',
                ('install_exe', 'install_dir'),
                ('force', 'force'),
                ('skip_build', 'skip_build'))

    def run(self):
        if not self.skip_build:
            self.run_command('build_exe')
        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)
        if sys.platform != "win32":
            baseDir = os.path.dirname(os.path.dirname(self.install_dir))
            binDir = os.path.join(baseDir, "bin")
            if not os.path.exists(binDir):
                os.makedirs(binDir)
            sourceDir = os.path.join("..", self.install_dir[len(baseDir) + 1:])
            for executable in self.distribution.executables:
                name = os.path.basename(executable.targetName)
                source = os.path.join(sourceDir, name)
                target = os.path.join(binDir, name)
                if os.path.exists(target):
                    os.unlink(target)
                os.symlink(source, target)
                self.outfiles.append(target)

    def get_inputs(self):
        return self.distribution.executables or []

    def get_outputs(self):
        return self.outfiles or []


def _AddCommandClass(commandClasses, name, cls):
    if name not in commandClasses:
        commandClasses[name] = cls


def setup(**attrs):
    attrs["distclass"] = Distribution
    commandClasses = attrs.setdefault("cmdclass", {})
    if sys.platform == "win32":
        if sys.version_info[:2] >= (2, 5):
            _AddCommandClass(commandClasses, "bdist_msi", cx_Freeze.bdist_msi)
    else:
        _AddCommandClass(commandClasses, "bdist_rpm", cx_Freeze.bdist_rpm)
    _AddCommandClass(commandClasses, "build", build)
    _AddCommandClass(commandClasses, "build_exe", build_exe)
    _AddCommandClass(commandClasses, "install", install)
    _AddCommandClass(commandClasses, "install_exe", install_exe)
    distutils.core.setup(**attrs)

