#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Embedded console for debugging.
'''

import sys, os, functools
from calibre.utils.config import OptionParser
from calibre.constants import iswindows
from calibre import prints
from calibre.startup import get_debug_executable
from polyglot.builtins import exec_path


def run_calibre_debug(*args, **kw):
    import subprocess
    creationflags = 0
    if iswindows:
        creationflags = subprocess.CREATE_NO_WINDOW
    cmd = get_debug_executable() + list(args)
    kw['creationflags'] = creationflags
    return subprocess.Popen(cmd, **kw)


def option_parser():
    parser = OptionParser(usage=_('''\
{0}

Various command line interfaces useful for debugging calibre. With no options,
this command starts an embedded Python interpreter. You can also run the main
calibre GUI, the calibre E-book viewer and the calibre editor in debug mode.

It also contains interfaces to various bits of calibre that do not have
dedicated command line tools, such as font subsetting, the E-book diff tool and so
on.

You can also use %prog to run standalone scripts. To do that use it like this:

    {1}

Everything after the -- is passed to the script. You can also use calibre-debug
as a shebang in scripts, like this:

    {2}
''').format(_('%prog [options]'), '%prog -e myscript.py -- --option1 --option2 file1 file2 ...', '#!/usr/bin/env -S calibre-debug -e -- --'))
    parser.add_option('-c', '--command', help=_('Run Python code.'))
    parser.add_option('-e', '--exec-file', help=_('Run the Python code in file.'))
    parser.add_option('-f', '--subset-font', action='store_true', default=False,
                      help=_('Subset the specified font. Use -- after this option to pass option to the font subsetting program.'))
    parser.add_option('-d', '--debug-device-driver', default=False, action='store_true',
                      help=_('Debug device detection'))
    parser.add_option('-g', '--gui',  default=False, action='store_true',
                      help=_('Run the GUI with debugging enabled. Debug output is '
                      'printed to stdout and stderr.'))
    parser.add_option('--gui-debug',  default=None,
                      help=_('Run the GUI with a debug console, logging to the'
                      ' specified path. For internal use only, use the -g'
                      ' option to run the GUI in debug mode'))
    parser.add_option('--run-without-debug', default=False, action='store_true', help=_('Don\'t run with the DEBUG flag set'))
    parser.add_option('-w', '--viewer',  default=False, action='store_true',
                      help=_('Run the E-book viewer in debug mode'))
    parser.add_option('--paths', default=False, action='store_true',
            help=_('Output the paths necessary to setup the calibre environment'))
    parser.add_option('--add-simple-plugin', default=None,
            help=_('Add a simple plugin (i.e. a plugin that consists of only a '
            '.py file), by specifying the path to the py file containing the '
            'plugin code.'))
    parser.add_option('-m', '--inspect-mobi', action='store_true',
            default=False,
            help=_('Inspect the MOBI file(s) at the specified path(s)'))
    parser.add_option('-t', '--edit-book', action='store_true',
            help=_('Launch the calibre "Edit book" tool in debug mode.'))
    parser.add_option('-x', '--explode-book', default=False, action='store_true',
            help=_('Explode the book into the specified folder.\nUsage: '
            '-x file.epub output_dir\n'
            'Exports the book as a collection of HTML '
            'files and metadata, which you can edit using standard HTML '
            'editing tools. Works with EPUB, AZW3, HTMLZ and DOCX files.'))
    parser.add_option('-i', '--implode-book', default=False, action='store_true', help=_(
        'Implode a previously exploded book.\nUsage: -i output_dir file.epub\n'
        'Imports the book from the files in output_dir which must have'
        ' been created by a previous call to --explode-book. Be sure to'
        ' specify the same file type as was used when exploding.'))
    parser.add_option('--export-all-calibre-data', default=False, action='store_true',
        help=_('Export all calibre data (books/settings/plugins). Normally, you will'
            ' be asked for the export folder and the libraries to export. You can also specify them'
            ' as command line arguments to skip the questions.'
            ' Use absolute paths for the export folder and libraries.'
            ' The special keyword "all" can be used to export all libraries. Examples:\n\n'
            '  calibre-debug --export-all-calibre-data  # for interactive use\n'
            '  calibre-debug --export-all-calibre-data /path/to/empty/export/folder /path/to/library/folder1 /path/to/library2\n'
            '  calibre-debug --export-all-calibre-data /export/folder all  # export all known libraries'
    ))
    parser.add_option('--import-calibre-data', default=False, action='store_true',
        help=_('Import previously exported calibre data'))
    parser.add_option('-s', '--shutdown-running-calibre', default=False,
            action='store_true',
            help=_('Cause a running calibre instance, if any, to be'
                ' shutdown. Note that if there are running jobs, they '
                'will be silently aborted, so use with care.'))
    parser.add_option('--test-build', help=_('Test binary modules in build'),
            action='store_true', default=False)
    parser.add_option('-r', '--run-plugin', help=_(
        'Run a plugin that provides a command line interface. For example:\n'
        'calibre-debug -r "Plugin name" -- file1 --option1\n'
        'Everything after the -- will be passed to the plugin as arguments.'))
    parser.add_option('-t', '--run-test', help=_(
        'Run the named test(s). Use the special value "all" to run all tests.'
        ' If the test name starts with a period it is assumed to be a module name.'
        ' If the test name starts with @ it is assumed to be a category name.'
    ))
    parser.add_option('--diff', action='store_true', default=False, help=_(
        'Run the calibre diff tool. For example:\n'
        'calibre-debug --diff file1 file2'))
    parser.add_option('--default-programs', default=None, choices=['register', 'unregister'],
                          help=_('(Un)register calibre from Windows Default Programs.') + ' --default-programs=(register|unregister)')
    parser.add_option('--fix-multiprocessing', default=False, action='store_true',
        help=_('For internal use'))

    return parser


def debug_device_driver():
    from calibre.devices import debug
    debug(ioreg_to_tmp=True, buf=sys.stdout)
    if iswindows:  # no2to3
        input('Press Enter to continue...')  # no2to3


def add_simple_plugin(path_to_plugin):
    import tempfile, zipfile, shutil
    tdir = tempfile.mkdtemp()
    open(os.path.join(tdir, 'custom_plugin.py'),
            'wb').write(open(path_to_plugin, 'rb').read())
    odir = os.getcwd()
    os.chdir(tdir)
    zf = zipfile.ZipFile('plugin.zip', 'w')
    zf.write('custom_plugin.py')
    zf.close()
    from calibre.customize.ui import main
    main(['calibre-customize', '-a', 'plugin.zip'])
    os.chdir(odir)
    shutil.rmtree(tdir)


def print_basic_debug_info(out=None):
    if out is None:
        out = sys.stdout
    out = functools.partial(prints, file=out)
    import platform
    from calibre.constants import (__appname__, get_version, isportable, ismacos,
                                   isfrozen)
    from calibre.utils.localization import set_translators
    out(__appname__, get_version(), 'Portable' if isportable else '',
        'embedded-python:', isfrozen)
    out(platform.platform(), platform.system(), platform.architecture())
    out(platform.system_alias(platform.system(), platform.release(),
            platform.version()))
    out('Python', platform.python_version())
    try:
        if iswindows:
            out('Windows:', platform.win32_ver())
        elif ismacos:
            out('OSX:', platform.mac_ver())
        else:
            out('Linux:', platform.linux_distribution())
    except:
        pass
    out('Interface language:', str(set_translators.lang))
    from calibre.customize.ui import has_external_plugins, initialized_plugins
    if has_external_plugins():
        from calibre.customize import PluginInstallationType
        names = (f'{p.name} {p.version}' for p in initialized_plugins()
                 if getattr(p, 'installation_type', None) is not PluginInstallationType.BUILTIN)
        out('Successfully initialized third party plugins:', ' && '.join(names))


def run_debug_gui(logpath):
    import time
    time.sleep(3)  # Give previous GUI time to shutdown fully and release locks
    from calibre.constants import __appname__
    prints(__appname__, _('Debug log'))
    print_basic_debug_info()
    from calibre.gui_launch import calibre
    calibre(['__CALIBRE_GUI_DEBUG__', logpath])


def load_user_plugins():
    # Load all user defined plugins so the script can import from the
    # calibre_plugins namespace
    import calibre.customize.ui as dummy
    return dummy


def run_script(path, args):
    load_user_plugins()
    sys.argv = [path] + args
    ef = os.path.abspath(path)
    if '/src/calibre/' not in ef.replace(os.pathsep, '/'):
        base = os.path.dirname(ef)
        sys.path.insert(0, base)
    g = globals()
    g['__name__'] = '__main__'
    g['__file__'] = ef
    exec_path(ef, g)


def inspect_mobi(path):
    from calibre.ebooks.mobi.debug.main import inspect_mobi
    prints('Inspecting:', path)
    inspect_mobi(path)
    print()


def main(args=sys.argv):
    from calibre.constants import debug

    opts, args = option_parser().parse_args(args)
    if opts.fix_multiprocessing:
        sys.argv = [sys.argv[0], '--multiprocessing-fork']
        exec(args[-1])
        return
    if not opts.run_without_debug:
        debug()
    if opts.gui:
        from calibre.gui_launch import calibre
        calibre(['calibre'] + args[1:])
    elif opts.gui_debug is not None:
        run_debug_gui(opts.gui_debug)
    elif opts.viewer:
        from calibre.gui_launch import ebook_viewer
        ebook_viewer(['ebook-viewer'] + args[1:])
    elif opts.command:
        sys.argv = args
        exec(opts.command)
    elif opts.debug_device_driver:
        debug_device_driver()
    elif opts.add_simple_plugin is not None:
        add_simple_plugin(opts.add_simple_plugin)
    elif opts.paths:
        prints('CALIBRE_RESOURCES_PATH='+sys.resources_location)
        prints('CALIBRE_EXTENSIONS_PATH='+sys.extensions_location)
        prints('CALIBRE_PYTHON_PATH='+os.pathsep.join(sys.path))
    elif opts.inspect_mobi:
        for path in args[1:]:
            inspect_mobi(path)
    elif opts.edit_book:
        from calibre.gui_launch import ebook_edit
        ebook_edit(['ebook-edit'] + args[1:])
    elif opts.explode_book or opts.implode_book:
        from calibre.ebooks.tweak import explode, implode
        try:
            a1, a2 = args[1:]
        except Exception:
            raise SystemExit('Must provide exactly two arguments')
        f = explode if opts.explode_book else implode
        f(a1, a2)
    elif opts.test_build:
        from calibre.test_build import test, test_multiprocessing
        test_multiprocessing()
        test()
    elif opts.shutdown_running_calibre:
        from calibre.gui2.main import shutdown_other
        shutdown_other()
    elif opts.subset_font:
        from calibre.utils.fonts.sfnt.subset import main
        main(['subset-font'] + args[1:])
    elif opts.exec_file:
        if opts.exec_file == '--':
            run_script(args[1], args[2:])
        else:
            run_script(opts.exec_file, args[1:])
    elif opts.run_plugin:
        from calibre.customize.ui import find_plugin
        plugin = find_plugin(opts.run_plugin)
        if plugin is None:
            prints(_('No plugin named %s found')%opts.run_plugin)
            raise SystemExit(1)
        plugin.cli_main([plugin.name] + args[1:])
    elif opts.run_test:
        debug(False)
        from calibre.utils.run_tests import run_test
        run_test(opts.run_test)
    elif opts.diff:
        from calibre.gui2.tweak_book.diff.main import main
        main(['calibre-diff'] + args[1:])
    elif opts.default_programs:
        if not iswindows:
            raise SystemExit('Can only be run on Microsoft Windows')
        if opts.default_programs == 'register':
            from calibre.utils.winreg.default_programs import register as func
        else:
            from calibre.utils.winreg.default_programs import unregister as func
        print('Running', func.__name__, '...')
        func()
    elif opts.export_all_calibre_data:
        args = args[1:]
        from calibre.utils.exim import run_exporter
        run_exporter(args=args, check_known_libraries=False)
    elif opts.import_calibre_data:
        from calibre.utils.exim import run_importer
        run_importer()
    elif len(args) >= 2 and args[1].rpartition('.')[-1] in {'py', 'recipe'}:
        run_script(args[1], args[2:])
    elif len(args) >= 2 and args[1].rpartition('.')[-1] in {'mobi', 'azw', 'azw3', 'docx', 'odt'}:
        for path in args[1:]:
            ext = path.rpartition('.')[-1]
            if ext in {'docx', 'odt'}:
                from calibre.ebooks.docx.dump import dump
                dump(path)
            elif ext in {'mobi', 'azw', 'azw3'}:
                inspect_mobi(path)
            else:
                print('Cannot dump unknown filetype: %s' % path)
    elif len(args) >= 2 and os.path.exists(os.path.join(args[1], '__main__.py')):
        sys.path.insert(0, args[1])
        run_script(os.path.join(args[1], '__main__.py'), args[2:])
    else:
        load_user_plugins()
        from calibre import ipython
        ipython()

    return 0


if __name__ == '__main__':
    sys.exit(main())
