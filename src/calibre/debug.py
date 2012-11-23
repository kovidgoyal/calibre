#!/usr/bin/env  python

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
    parser = OptionParser(usage='''\
%prog [options]

Various command line interfaces useful for debugging calibre. With no options,
this command starts an embedded python interpreter. You can also run the main
calibre GUI and the calibre viewer in debug mode.

It also contains interfaces to various bits of calibre that do not have
dedicated command line tools, such as font subsetting, tweaking ebooks and so
on.
''')
    parser.add_option('-c', '--command', help='Run python code.', default=None)
    parser.add_option('-e', '--exec-file', default=None, help='Run the python code in file.')
    parser.add_option('-f', '--subset-font', default=False,
            action='store_true', help='Subset the specified font')
    parser.add_option('-d', '--debug-device-driver', default=False, action='store_true',
                      help='Debug the specified device driver.')
    parser.add_option('-g', '--gui',  default=False, action='store_true',
                      help='Run the GUI with debugging enabled. Debug output is '
                      'printed to stdout and stderr.')
    parser.add_option('--gui-debug',  default=None,
                      help='Run the GUI with a debug console, logging to the'
                      ' specified path. For internal use only, use the -g'
                      ' option to run the GUI in debug mode',)
    parser.add_option('--show-gui-debug',  default=None,
                      help='Display the specified log file. For internal use'
                      ' only.',)
    parser.add_option('-w', '--viewer',  default=False, action='store_true',
                      help='Run the ebook viewer',)
    parser.add_option('--paths', default=False, action='store_true',
            help='Output the paths necessary to setup the calibre environment')
    parser.add_option('--add-simple-plugin', default=None,
            help='Add a simple plugin (i.e. a plugin that consists of only a '
            '.py file), by specifying the path to the py file containing the '
            'plugin code.')
    parser.add_option('--reinitialize-db', default=None,
            help='Re-initialize the sqlite calibre database at the '
            'specified path. Useful to recover from db corruption.'
            ' You can also specify the path to an SQL dump which '
            'will be used instead of trying to dump the database.'
            ' This can be useful when dumping fails, but dumping '
            'with sqlite3 works.')
    parser.add_option('-p', '--py-console', help='Run python console',
            default=False, action='store_true')
    parser.add_option('-m', '--inspect-mobi', action='store_true',
            default=False,
            help='Inspect the MOBI file(s) at the specified path(s)')
    parser.add_option('--tweak-book', default=None,
            help='Tweak the book (exports the book as a collection of HTML '
            'files and metadata, which you can edit using standard HTML '
            'editing tools, and then rebuilds the file from the edited HTML. '
            'Makes no additional changes to the HTML, unlike a full calibre '
            'conversion).')
    parser.add_option('-s', '--shutdown-running-calibre', default=False,
            action='store_true',
            help=_('Cause a running calibre instance, if any, to be'
                ' shutdown. Note that if there are running jobs, they '
                'will be silently aborted, so use with care.'))

    parser.add_option('--test-build', help='Test binary modules in build',
            action='store_true', default=False)

    return parser

def reinit_db(dbpath, callback=None, sql_dump=None):
    if not os.path.exists(dbpath):
        raise ValueError(dbpath + ' does not exist')
    from calibre.library.sqlite import connect
    from contextlib import closing
    import shutil
    conn = connect(dbpath, False)
    uv = conn.get('PRAGMA user_version;', all=False)
    conn.execute('PRAGMA writable_schema=ON')
    conn.commit()
    if sql_dump is None:
        sql_lines = conn.dump()
    else:
        sql_lines = open(sql_dump, 'rb').read()
    conn.close()
    dest = dbpath + '.tmp'
    try:
        with closing(connect(dest, False)) as nconn:
            nconn.execute('create temporary table temp_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT)')
            nconn.commit()
            if sql_dump is None:
                if callable(callback):
                    callback(len(sql_lines), True)
                for i, line in enumerate(sql_lines):
                    try:
                        nconn.execute(line)
                    except:
                        import traceback
                        prints('SQL line %r failed with error:'%line)
                        prints(traceback.format_exc())
                        continue
                    finally:
                        if callable(callback):
                            callback(i, False)
            else:
                nconn.executescript(sql_lines)
            nconn.execute('pragma user_version=%d'%int(uv))
            nconn.commit()
        os.remove(dbpath)
        shutil.copyfile(dest, dbpath)
    finally:
        if os.path.exists(dest):
            os.remove(dest)
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
    if out is None: out = sys.stdout
    out = functools.partial(prints, file=out)
    import platform
    from calibre.constants import __appname__, get_version, isportable, isosx
    out(__appname__, get_version(), 'Portable' if isportable else '')
    out(platform.platform(), platform.system())
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

def run_debug_gui(logpath):
    import time
    time.sleep(3) # Give previous GUI time to shutdown fully and release locks
    from calibre.constants import __appname__
    prints(__appname__, _('Debug log'))
    print_basic_debug_info()
    from calibre.gui2.main import main
    main(['__CALIBRE_GUI_DEBUG__', logpath])

def main(args=sys.argv):
    from calibre.constants import debug
    debug()
    if len(args) > 2 and args[1] in ('-e', '--exec-file'):

        # Load all plugins user defined plugins so the script can import from the
        # calibre_plugins namespace
        import calibre.customize.ui as dummy
        dummy

        sys.argv = [args[2]] + args[3:]
        ef = os.path.abspath(args[2])
        base = os.path.dirname(ef)
        sys.path.insert(0, base)
        g = globals()
        g['__name__'] = '__main__'
        g['__file__'] = ef
        execfile(ef, g)
        return

    if len(args) > 1 and args[1] in ('-f', '--subset-font'):
        from calibre.utils.fonts.sfnt.subset import main
        main(['subset-font']+args[2:])
        return

    opts, args = option_parser().parse_args(args)
    if opts.gui:
        from calibre.gui2.main import main
        print_basic_debug_info()
        main(['calibre'])
    elif opts.gui_debug is not None:
        run_debug_gui(opts.gui_debug)
    elif opts.show_gui_debug:
        import time, re
        time.sleep(1)
        from calibre.gui2 import open_local_file
        if iswindows:
            with open(opts.show_gui_debug, 'r+b') as f:
                raw = f.read()
                raw = re.sub('(?<!\r)\n', '\r\n', raw)
                f.seek(0)
                f.truncate()
                f.write(raw)
        open_local_file(opts.show_gui_debug)
    elif opts.viewer:
        from calibre.gui2.viewer.main import main
        vargs = ['ebook-viewer', '--debug-javascript']
        if len(args) > 1:
            vargs.append(args[-1])
        main(vargs)
    elif opts.py_console:
        from calibre.utils.pyconsole.main import main
        main()
    elif opts.command:
        sys.argv = args
        exec opts.command
    elif opts.debug_device_driver:
        debug_device_driver()
    elif opts.add_simple_plugin is not None:
        add_simple_plugin(opts.add_simple_plugin)
    elif opts.paths:
        prints('CALIBRE_RESOURCES_PATH='+sys.resources_location)
        prints('CALIBRE_EXTENSIONS_PATH='+sys.extensions_location)
        prints('CALIBRE_PYTHON_PATH='+os.pathsep.join(sys.path))
    elif opts.reinitialize_db is not None:
        sql_dump = None
        if len(args) > 1 and os.access(args[-1], os.R_OK):
            sql_dump = args[-1]
        reinit_db(opts.reinitialize_db, sql_dump=sql_dump)
    elif opts.inspect_mobi:
        from calibre.ebooks.mobi.debug.main import inspect_mobi
        for path in args[1:]:
            prints('Inspecting:', path)
            inspect_mobi(path)
            print
    elif opts.tweak_book:
        from calibre.ebooks.tweak import tweak
        tweak(opts.tweak_book)
    elif opts.test_build:
        from calibre.test_build import test
        test()
    elif opts.shutdown_running_calibre:
        from calibre.gui2.main import shutdown_other
        shutdown_other()
    else:
        from calibre import ipython
        ipython()

    return 0

if __name__ == '__main__':
    sys.exit(main())
