#!/usr/bin/env  python2

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Embedded console for debugging.
'''

import sys, os, functools
from calibre.utils.config import OptionParser
from calibre.constants import iswindows
from calibre import prints


def option_parser():
    parser = OptionParser(usage=_('''\
{0}

Various command line interfaces useful for debugging calibre. With no options,
this command starts an embedded python interpreter. You can also run the main
calibre GUI, the calibre viewer and the calibre editor in debug mode.

It also contains interfaces to various bits of calibre that do not have
dedicated command line tools, such as font subsetting, the ebook diff tool and so
on.

You can also use %prog to run standalone scripts. To do that use it like this:

    {1}

Everything after the -- is passed to the script.
''').format(_('%prog [options]'), '%prog myscript.py -- --option1 --option2 file1 file2 ...'))
    parser.add_option('-c', '--command', help=_('Run python code.'))
    parser.add_option('-e', '--exec-file', help=_('Run the python code in file.'))
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
    parser.add_option('-w', '--viewer',  default=False, action='store_true',
                      help=_('Run the ebook viewer in debug mode'))
    parser.add_option('--paths', default=False, action='store_true',
            help=_('Output the paths necessary to setup the calibre environment'))
    parser.add_option('--add-simple-plugin', default=None,
            help=_('Add a simple plugin (i.e. a plugin that consists of only a '
            '.py file), by specifying the path to the py file containing the '
            'plugin code.'))
    parser.add_option('--reinitialize-db', default=None,
            help=_('Re-initialize the sqlite calibre database at the '
            'specified path. Useful to recover from db corruption.'))
    parser.add_option('-m', '--inspect-mobi', action='store_true',
            default=False,
            help=_('Inspect the MOBI file(s) at the specified path(s)'))
    parser.add_option('-t', '--edit-book', action='store_true',
            help=_('Launch the calibre "Edit book" tool in debug mode.'))
    parser.add_option('-x', '--explode-book', default=None,
            help=_('Explode the book (exports the book as a collection of HTML '
            'files and metadata, which you can edit using standard HTML '
            'editing tools, and then rebuilds the file from the edited HTML. '
            'Makes no additional changes to the HTML, unlike a full calibre '
            'conversion).'))
    parser.add_option('--export-all-calibre-data', default=False, action='store_true',
        help=_('Export all calibre data (books/settings/plugins)'))
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
        'calibre-debug -r "Add Books" -- file1 --option1\n'
        'Everything after the -- will be passed to the plugin as arguments.'))
    parser.add_option('--diff', action='store_true', default=False, help=_(
        'Run the calibre diff tool. For example:\n'
        'calibre-debug --diff file1 file2'))
    parser.add_option('--default-programs', default=None, choices=['register', 'unregister'],
                          help=_('(Un)register calibre from Windows Default Programs.') + ' --default-programs=(register|unregister)')
    parser.add_option('--new-server', action='store_true',
        help='Run the new calibre content server. Any options specified after a -- will be passed to the server.')

    return parser


def reinit_db(dbpath):
    from contextlib import closing
    from calibre import as_unicode
    from calibre.ptempfile import TemporaryFile
    from calibre.utils.filenames import atomic_rename
    # We have to use sqlite3 instead of apsw as apsw has no way to discard
    # problematic statements
    import sqlite3
    from calibre.library.sqlite import do_connect
    with TemporaryFile(suffix='_tmpdb.db', dir=os.path.dirname(dbpath)) as tmpdb:
        with closing(do_connect(dbpath)) as src, closing(do_connect(tmpdb)) as dest:
            dest.execute('create temporary table temp_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT)')
            dest.commit()
            uv = int(src.execute('PRAGMA user_version;').fetchone()[0])
            dump = src.iterdump()
            last_restore_error = None
            while True:
                try:
                    statement = next(dump)
                except StopIteration:
                    break
                except sqlite3.OperationalError as e:
                    prints('Failed to dump a line:', as_unicode(e))
                if last_restore_error:
                    prints('Failed to restore a line:', last_restore_error)
                    last_restore_error = None
                try:
                    dest.execute(statement)
                except sqlite3.OperationalError as e:
                    last_restore_error = as_unicode(e)
                    # The dump produces an extra commit at the end, so
                    # only print this error if there are more
                    # statements to be restored
            dest.execute('PRAGMA user_version=%d;'%uv)
            dest.commit()
        atomic_rename(tmpdb, dbpath)
    prints('Database successfully re-initialized')


def debug_device_driver():
    from calibre.devices import debug
    debug(ioreg_to_tmp=True, buf=sys.stdout)
    if iswindows:
        raw_input('Press Enter to continue...')


def add_simple_plugin(path_to_plugin):
    import tempfile, zipfile, shutil
    tdir = tempfile.mkdtemp()
    open(os.path.join(tdir, 'custom_plugin.py'),
            'wb').write(open(path_to_plugin, 'rb').read())
    odir = os.getcwdu()
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
    from calibre.constants import (__appname__, get_version, isportable, isosx,
                                   isfrozen, is64bit)
    out(__appname__, get_version(), 'Portable' if isportable else '',
        'embedded-python:', isfrozen, 'is64bit:', is64bit)
    out(platform.platform(), platform.system(), platform.architecture())
    if iswindows and not is64bit:
        try:
            import win32process
            if win32process.IsWow64Process():
                out('32bit process running on 64bit windows')
        except:
            pass
    out(platform.system_alias(platform.system(), platform.release(),
            platform.version()))
    out('Python', platform.python_version())
    try:
        if iswindows:
            out('Windows:', platform.win32_ver())
        elif isosx:
            out('OSX:', platform.mac_ver())
        else:
            out('Linux:', platform.linux_distribution())
    except:
        pass
    from calibre.customize.ui import has_external_plugins, initialized_plugins
    if has_external_plugins():
        names = ('{0} {1}'.format(p.name, p.version) for p in initialized_plugins() if getattr(p, 'plugin_path', None) is not None)
        out('Successfully initialized third party plugins:', ' && '.join(names))


def run_debug_gui(logpath):
    import time
    time.sleep(3)  # Give previous GUI time to shutdown fully and release locks
    from calibre.constants import __appname__
    prints(__appname__, _('Debug log'))
    print_basic_debug_info()
    from calibre.gui_launch import calibre
    calibre(['__CALIBRE_GUI_DEBUG__', logpath])


def run_script(path, args):
    # Load all user defined plugins so the script can import from the
    # calibre_plugins namespace
    import calibre.customize.ui as dummy
    dummy

    sys.argv = [path] + args
    ef = os.path.abspath(path)
    if '/src/calibre/' not in ef.replace(os.pathsep, '/'):
        base = os.path.dirname(ef)
        sys.path.insert(0, base)
    g = globals()
    g['__name__'] = '__main__'
    g['__file__'] = ef
    execfile(ef, g)


def inspect_mobi(path):
    from calibre.ebooks.mobi.debug.main import inspect_mobi
    prints('Inspecting:', path)
    inspect_mobi(path)
    print


def main(args=sys.argv):
    from calibre.constants import debug
    debug()

    opts, args = option_parser().parse_args(args)
    if opts.gui:
        from calibre.gui_launch import calibre
        print_basic_debug_info()
        calibre(['calibre'])
    elif opts.gui_debug is not None:
        run_debug_gui(opts.gui_debug)
    elif opts.viewer:
        from calibre.gui_launch import ebook_viewer
        ebook_viewer(['ebook-viewer', '--debug-javascript'] + args[1:])
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
    elif opts.reinitialize_db is not None:
        reinit_db(opts.reinitialize_db)
    elif opts.inspect_mobi:
        for path in args[1:]:
            inspect_mobi(path)
    elif opts.edit_book:
        from calibre.gui_launch import ebook_edit
        ebook_edit(['ebook-edit'] + args[1:])
    elif opts.explode_book:
        from calibre.ebooks.tweak import tweak
        tweak(opts.explode_book)
    elif opts.test_build:
        from calibre.test_build import test
        test()
    elif opts.shutdown_running_calibre:
        from calibre.gui2.main import shutdown_other
        shutdown_other()
    elif opts.subset_font:
        from calibre.utils.fonts.sfnt.subset import main
        main(['subset-font'] + args[1:])
    elif opts.exec_file:
        run_script(opts.exec_file, args[1:])
    elif opts.run_plugin:
        from calibre.customize.ui import find_plugin
        plugin = find_plugin(opts.run_plugin)
        if plugin is None:
            prints(_('No plugin named %s found')%opts.run_plugin)
            raise SystemExit(1)
        plugin.cli_main([plugin.name] + args[1:])
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
        print 'Running', func.__name__, '...'
        func()
    elif opts.new_server:
        from calibre.srv.standalone import main
        main(args)
    elif opts.export_all_calibre_data:
        from calibre.utils.exim import run_exporter
        run_exporter()
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
                print ('Cannot dump unknown filetype: %s' % path)
    elif len(args) >= 2 and os.path.exists(os.path.join(args[1], '__main__.py')):
        sys.path.insert(0, args[1])
        run_script(os.path.join(args[1], '__main__.py'), args[2:])
    else:
        from calibre import ipython
        ipython()

    return 0


if __name__ == '__main__':
    sys.exit(main())
