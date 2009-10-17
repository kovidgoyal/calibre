#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Embedded console for debugging.
'''

import sys, os
from calibre.utils.config import OptionParser
from calibre.constants import iswindows, isosx
from calibre import prints

def option_parser():
    parser = OptionParser(usage='''\
%prog [options]

Run an embedded python interpreter.
''')
    parser.add_option('-c', '--command', help='Run python code.', default=None)
    parser.add_option('-e', '--exec-file', default=None, help='Run the python code in file.')
    parser.add_option('-d', '--debug-device-driver', default=False, action='store_true',
                      help='Debug the specified device driver.')
    parser.add_option('-g', '--gui',  default=False, action='store_true',
                      help='Run the GUI',)
    parser.add_option('--paths', default=False, action='store_true',
            help='Output the paths necessary to setup the calibre environment')
    parser.add_option('--migrate', action='store_true', default=False,
                      help='Migrate old database. Needs two arguments. Path '
                           'to library1.db and path to new library folder.')
    parser.add_option('--add-simple-plugin', default=None,
            help='Add a simple plugin (i.e. a plugin that consists of only a '
            '.py file), by specifying the path to the py file containing the '
            'plugin code.')
    parser.add_option('--pdfreflow', default=None,
            help='Path to PDF file to try and reflow. Output will be placed in '
            'current directory. ')
    parser.add_option('-f', '--develop-from', default=None,
            help=('Develop calibre from the specified path. '
                'The path should point to the src sub-directory in the '
                'calibre source tree.'))

    return parser

def develop_from(path):
    from calibre.gui2 import build_forms
    print 'Compiling .ui forms...'
    build_forms(path)

def migrate(old, new):
    from calibre.utils.config import prefs
    from calibre.library.database import LibraryDatabase
    from calibre.library.database2 import LibraryDatabase2
    from calibre.utils.terminfo import ProgressBar
    from calibre import terminal_controller
    class Dummy(ProgressBar):
        def setLabelText(self, x): pass
        def setAutoReset(self, y): pass
        def reset(self): pass
        def setRange(self, min, max):
            self.min = min
            self.max = max
        def setValue(self, val):
            self.update(float(val)/getattr(self, 'max', 1))

    db = LibraryDatabase(old)
    db2 = LibraryDatabase2(new)
    db2.migrate_old(db, Dummy(terminal_controller, 'Migrating database...'))
    prefs['library_path'] = os.path.abspath(new)
    print 'Database migrated to', os.path.abspath(new)

def debug_device_driver():
    from calibre.customize.ui import device_plugins
    from calibre.devices.scanner import DeviceScanner
    s = DeviceScanner()
    s.scan()
    print 'USB devices on system:', repr(s.devices)
    if iswindows:
        wmi = __import__('wmi', globals(), locals(), [], -1)
        drives = []
        print 'Drives detected:'
        print '\t', '(ID, Partitions, Drive letter)'
        for drive in wmi.WMI().Win32_DiskDrive():
            if drive.Partitions == 0:
                continue
            try:
                partition = drive.associators("Win32_DiskDriveToDiskPartition")[0]
                logical_disk = partition.associators('Win32_LogicalDiskToPartition')[0]
                prefix = logical_disk.DeviceID+os.sep
                drives.append((str(drive.PNPDeviceID), drive.Index, prefix))
            except IndexError:
                drives.append((str(drive.PNPDeviceID), 'No mount points found'))
        for drive in drives:
            print '\t', drive
    if isosx:
        from calibre.devices.usbms.device import Device
        raw = Device.run_ioreg()
        open('/tmp/ioreg.txt', 'wb').write(raw)
        print 'ioreg output saved to /tmp/ioreg.txt'
    connected_devices = []
    for dev in device_plugins():
        print 'Looking for', dev.__class__.__name__
        connected = s.is_device_connected(dev)
        if connected:
            connected_devices.append(dev)

    errors = {}
    success = False
    for dev in connected_devices:
        print 'Device possibly connected:', dev
        print 'Trying to open device...',
        try:
            dev.open()
            print 'OK'
        except:
            import traceback
            errors[dev] = traceback.format_exc()
            print 'failed'
            continue
        success = True
        if hasattr(dev, '_main_prefix'):
            print 'Main memory:', repr(dev._main_prefix)
        print 'Total space:', dev.total_space()
        break
    if not success and errors:
        print 'Opening of the following devices failed'
        for dev,msg in errors.items():
            print dev
            print msg
            print
    if isosx and os.path.exists('/tmp/ioreg.txt'):
        print
        print
        print "Don't forget to send the file /tmp/ioreg.txt as well"

    if iswindows:
        raw_input('Press Enter to continue...')


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



def main(args=sys.argv):
    from calibre.constants import debug
    debug()
    opts, args = option_parser().parse_args(args)
    if opts.gui:
        from calibre.gui2.main import main
        main(['calibre'])
    elif opts.command:
        sys.argv = args[:1]
        exec opts.command
    elif opts.exec_file:
        sys.argv = args[:1]
        base = os.path.dirname(os.path.abspath(opts.exec_file))
        sys.path.insert(0, base)
        execfile(opts.exec_file)
    elif opts.debug_device_driver:
        debug_device_driver()
    elif opts.migrate:
        if len(args) < 3:
            print 'You must specify the path to library1.db and the path to the new library folder'
            return 1
        migrate(args[1], args[2])
    elif opts.add_simple_plugin is not None:
        add_simple_plugin(opts.add_simple_plugin)
    elif opts.paths:
        prints('CALIBRE_RESOURCES_PATH='+sys.resources_location)
        prints('CALIBRE_EXTENSIONS_PATH='+sys.extensions_location)
        prints('CALIBRE_PYTHON_PATH='+os.pathsep.join(sys.path))
    elif opts.pdfreflow:
        from calibre.ebooks.pdf.reflow import option_parser as px, run
        from calibre.utils.logging import default_log
        opts2, args = px().parse_args(['xxxx', '-vvvv', opts.pdfreflow])
        run(opts2, opts.pdfreflow, default_log)
    elif opts.develop_from is not None:
        develop_from(opts.develop_from)
    else:
        from calibre.utils.config import config_dir
        ipydir = os.path.join(config_dir, ('_' if iswindows else '.')+'ipython')
        os.environ['IPYTHONDIR'] = ipydir
        from IPython.Shell import IPShellEmbed
        ipshell = IPShellEmbed()
        ipshell()



    return 0

if __name__ == '__main__':
    sys.exit(main())
