#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Provides a command-line interface to ebook devices.

For usage information run the script.
"""

import sys, time, os
from optparse import OptionParser

from calibre import __version__, __appname__, human_readable, fsync, prints
from calibre.devices.errors import ArgumentError, DeviceError, DeviceLocked
from calibre.customize.ui import device_plugins
from calibre.devices.scanner import DeviceScanner
from calibre.utils.config import device_prefs
from polyglot.builtins import unicode_type
from polyglot.io import PolyglotStringIO

MINIMUM_COL_WIDTH = 12  # : Minimum width of columns in ls output


class FileFormatter(object):

    def __init__(self, file):
        self.is_dir      = file.is_dir
        self.is_readonly = file.is_readonly
        self.size        = file.size
        self.ctime       = file.ctime
        self.wtime       = file.wtime
        self.name        = file.name
        self.path        = file.path

    @property
    def mode_string(self):
        """ The mode string for this file. There are only two modes read-only and read-write """
        mode, x = "-", "-"
        if self.is_dir:
            mode, x = "d", "x"
        if self.is_readonly:
            mode += "r-"+x+"r-"+x+"r-"+x
        else:
            mode += "rw"+x+"rw"+x+"rw"+x
        return mode

    @property
    def isdir_name(self):
        '''Return self.name + '/' if self is a directory'''
        name = self.name
        if self.is_dir:
            name += '/'
        return name

    @property
    def name_in_color(self):
        """ The name in ANSI text. Directories are blue, ebooks are green """
        cname = self.name
        blue, green, normal = "", "", ""
        if self.term:
            blue, green, normal = self.term.BLUE, self.term.GREEN, self.term.NORMAL
        if self.is_dir:
            cname = blue + self.name + normal
        else:
            ext = self.name[self.name.rfind("."):]
            if ext in (".pdf", ".rtf", ".lrf", ".lrx", ".txt"):
                cname = green + self.name + normal
        return cname

    @property
    def human_readable_size(self):
        """ File size in human readable form """
        return human_readable(self.size)

    @property
    def modification_time(self):
        """ Last modified time in the Linux ls -l format """
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.wtime))

    @property
    def creation_time(self):
        """ Last modified time in the Linux ls -l format """
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.ctime))


def info(dev):
    info = dev.get_device_information()
    print("Device name:     ", info[0])
    print("Device version:  ", info[1])
    print("Software version:", info[2])
    print("Mime type:       ", info[3])


def ls(dev, path, recurse=False, human_readable_size=False, ll=False, cols=0):
    def col_split(l, cols):  # split list l into columns
        rows = len(l) // cols
        if len(l) % cols:
            rows += 1
        m = []
        for i in range(rows):
            m.append(l[i::rows])
        return m

    def row_widths(table):  # Calculate widths for each column in the row-wise table
        tcols = len(table[0])
        rowwidths = [0 for i in range(tcols)]
        for row in table:
            c = 0
            for item in row:
                rowwidths[c] = len(item) if len(item) > rowwidths[c] else rowwidths[c]
                c += 1
        return rowwidths

    output = PolyglotStringIO()
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]
    dirs = dev.list(path, recurse)
    for dir in dirs:
        if recurse:
            prints(dir[0] + ":", file=output)
        lsoutput, lscoloutput = [], []
        files = dir[1]
        maxlen = 0
        if ll:  # Calculate column width for size column
            for file in files:
                size = len(unicode_type(file.size))
                if human_readable_size:
                    file = FileFormatter(file)
                    size = len(file.human_readable_size)
                if size > maxlen:
                    maxlen = size
        for file in files:
            file = FileFormatter(file)
            name = file.name if ll else file.isdir_name
            lsoutput.append(name)
            lscoloutput.append(name)
            if ll:
                size = unicode_type(file.size)
                if human_readable_size:
                    size = file.human_readable_size
                prints(file.mode_string, ("%"+unicode_type(maxlen)+"s")%size, file.modification_time, name, file=output)
        if not ll and len(lsoutput) > 0:
            trytable = []
            for colwidth in range(MINIMUM_COL_WIDTH, cols):
                trycols = int(cols//colwidth)
                trytable = col_split(lsoutput, trycols)
                works = True
                for row in trytable:
                    row_break = False
                    for item in row:
                        if len(item) > colwidth - 1:
                            works, row_break = False, True
                            break
                    if row_break:
                        break
                if works:
                    break
            rowwidths = row_widths(trytable)
            trytablecol = col_split(lscoloutput, len(trytable[0]))
            for r in range(len(trytable)):
                for c in range(len(trytable[r])):
                    padding = rowwidths[c] - len(trytable[r][c])
                    prints(trytablecol[r][c], "".ljust(padding), end=' ', file=output)
                prints(file=output)
        prints(file=output)
    listing = output.getvalue().rstrip() + "\n"
    output.close()
    return listing


def shutdown_plugins():
    for d in device_plugins():
        try:
            d.shutdown()
        except:
            pass


def main():
    from calibre.utils.terminal import geometry
    cols = geometry()[0]

    parser = OptionParser(usage="usage: %prog [options] command args\n\ncommand "+
            "is one of: info, books, df, ls, cp, mkdir, touch, cat, rm, eject, test_file\n\n"+
    "For help on a particular command: %prog command", version=__appname__+" version: " + __version__)
    parser.add_option("--log-packets", help="print out packet stream to stdout. "+
                    "The numbers in the left column are byte offsets that allow the packet size to be read off easily.",
    dest="log_packets", action="store_true", default=False)
    parser.remove_option("-h")
    parser.disable_interspersed_args()  # Allow unrecognized options
    options, args = parser.parse_args()

    if len(args) < 1:
        parser.print_help()
        return 1

    command = args[0]
    args = args[1:]
    dev = None
    scanner = DeviceScanner()
    scanner.scan()
    connected_devices = []

    for d in device_plugins():
        try:
            d.startup()
        except:
            print('Startup failed for device plugin: %s'%d)
        if d.MANAGES_DEVICE_PRESENCE:
            cd = d.detect_managed_devices(scanner.devices)
            if cd is not None:
                connected_devices.append((cd, d))
                dev = d
                break
            continue
        ok, det = scanner.is_device_connected(d)
        if ok:
            dev = d
            dev.reset(log_packets=options.log_packets, detected_device=det)
            connected_devices.append((det, dev))

    if dev is None:
        print('Unable to find a connected ebook reader.', file=sys.stderr)
        shutdown_plugins()
        return 1

    for det, d in connected_devices:
        try:
            d.open(det, None)
        except:
            continue
        else:
            dev = d
            d.specialize_global_preferences(device_prefs)
            break

    try:
        if command == "df":
            total = dev.total_space(end_session=False)
            free = dev.free_space()
            where = ("Memory", "Card A", "Card B")
            print("Filesystem\tSize \tUsed \tAvail \tUse%")
            for i in range(3):
                print("%-10s\t%s\t%s\t%s\t%s"%(where[i], human_readable(total[i]), human_readable(total[i]-free[i]), human_readable(free[i]),
                                                                            unicode_type(0 if total[i]==0 else int(100*(total[i]-free[i])/(total[i]*1.)))+"%"))
        elif command == 'eject':
            dev.eject()
        elif command == "books":
            print("Books in main memory:")
            for book in dev.books():
                print(book)
            print("\nBooks on storage carda:")
            for book in dev.books(oncard='carda'):
                print(book)
            print("\nBooks on storage cardb:")
            for book in dev.books(oncard='cardb'):
                print(book)
        elif command == "mkdir":
            parser = OptionParser(usage="usage: %prog mkdir [options] path\nCreate a directory on the device\n\npath must begin with / or card:/")
            if len(args) != 1:
                parser.print_help()
                sys.exit(1)
            dev.mkdir(args[0])
        elif command == "ls":
            parser = OptionParser(usage="usage: %prog ls [options] path\nList files on the device\n\npath must begin with / or card:/")
            parser.add_option(
                "-l", help="In addition to the name of each file, print the file type, permissions, and  timestamp  (the  modification time, in the local timezone). Times are local.",  # noqa
                dest="ll", action="store_true", default=False)
            parser.add_option("-R", help="Recursively list subdirectories encountered. /dev and /proc are omitted",
                              dest="recurse", action="store_true", default=False)
            parser.remove_option("-h")
            parser.add_option("-h", "--human-readable", help="show sizes in human readable format", dest="hrs", action="store_true", default=False)
            options, args = parser.parse_args(args)
            if len(args) != 1:
                parser.print_help()
                return 1
            print(ls(dev, args[0], recurse=options.recurse, ll=options.ll, human_readable_size=options.hrs, cols=cols), end=' ')
        elif command == "info":
            info(dev)
        elif command == "cp":
            usage="usage: %prog cp [options] source destination\nCopy files to/from the device\n\n"+\
            "One of source or destination must be a path on the device. \n\nDevice paths have the form\n"+\
            "dev:mountpoint/my/path\n"+\
            "where mountpoint is one of / or carda: or cardb:/\n\n"+\
            "source must point to a file for which you have read permissions\n"+\
            "destination must point to a file or directory for which you have write permissions"
            parser = OptionParser(usage=usage)
            parser.add_option('-f', '--force', dest='force', action='store_true', default=False,
                              help='Overwrite the destination file if it exists already.')
            options, args = parser.parse_args(args)
            if len(args) != 2:
                parser.print_help()
                return 1
            if args[0].startswith("dev:"):
                outfile = args[1]
                path = args[0][4:]
                if path.endswith("/"):
                    path = path[:-1]
                if os.path.isdir(outfile):
                    outfile = os.path.join(outfile, path[path.rfind("/")+1:])
                try:
                    outfile = lopen(outfile, "wb")
                except IOError as e:
                    print(e, file=sys.stderr)
                    parser.print_help()
                    return 1
                dev.get_file(path, outfile)
                fsync(outfile)
                outfile.close()
            elif args[1].startswith("dev:"):
                try:
                    infile = lopen(args[0], "rb")
                except IOError as e:
                    print(e, file=sys.stderr)
                    parser.print_help()
                    return 1
                dev.put_file(infile, args[1][4:], replace_file=options.force)
                infile.close()
            else:
                parser.print_help()
                return 1
        elif command == "cat":
            outfile = sys.stdout
            parser = OptionParser(
                usage="usage: %prog cat path\nShow file on the device\n\npath should point to a file on the device and must begin with /,a:/ or b:/")
            options, args = parser.parse_args(args)
            if len(args) != 1:
                parser.print_help()
                return 1
            if args[0].endswith("/"):
                path = args[0][:-1]
            else:
                path = args[0]
            outfile = sys.stdout
            dev.get_file(path, outfile)
        elif command == "rm":
            parser = OptionParser(usage="usage: %prog rm path\nDelete files from the device\n\npath should point to a file or empty directory on the device "+
                                  "and must begin with / or card:/\n\n"+
                                  "rm will DELETE the file. Be very CAREFUL")
            options, args = parser.parse_args(args)
            if len(args) != 1:
                parser.print_help()
                return 1
            dev.rm(args[0])
        elif command == "touch":
            parser = OptionParser(usage="usage: %prog touch path\nCreate an empty file on the device\n\npath should point to a file on the device and must begin with /,a:/ or b:/\n\n"+  # noqa
            "Unfortunately, I cant figure out how to update file times on the device, so if path already exists, touch does nothing")
            options, args = parser.parse_args(args)
            if len(args) != 1:
                parser.print_help()
                return 1
            dev.touch(args[0])
        elif command == 'test_file':
            parser = OptionParser(usage=("usage: %prog test_file path\n"
                'Open device, copy file specified by path to device and '
                'then eject device.'))
            options, args = parser.parse_args(args)
            if len(args) != 1:
                parser.print_help()
                return 1
            path = args[0]
            from calibre.ebooks.metadata.meta import get_metadata
            mi = get_metadata(lopen(path, 'rb'), path.rpartition('.')[-1].lower())
            print(dev.upload_books([args[0]], [os.path.basename(args[0])],
                    end_session=False, metadata=[mi]))
            dev.eject()
        else:
            parser.print_help()
            if getattr(dev, 'handle', False):
                dev.close()
            return 1
    except DeviceLocked:
        print("The device is locked. Use the --unlock option", file=sys.stderr)
    except (ArgumentError, DeviceError) as e:
        print(e, file=sys.stderr)
        return 1
    finally:
        shutdown_plugins()

    return 0


if __name__ == '__main__':
    main()
