#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
'''
import sys, time, subprocess, os, re
from setup import SRC, __appname__, __version__

INSTALLJAMMER = '/usr/local/installjammer/installjammer'

sv = re.sub(r'[a-z]\d+', '', __version__)

cmdline = [
    INSTALLJAMMER,
    '--build-dir', '/tmp/calibre-installjammer',
    '-DAppName', __appname__,
    '-DShortAppName', __appname__,
    '-DApplicationURL', 'http://%s.kovidgoyal.net'%__appname__,
    '-DCopyright', time.strftime('%Y Kovid Goyal'),
    '-DPackageDescription', '%s is an e-book library manager. It can view, convert and catalog e-books in most of the major e-book formats. It can also talk to e-book reader devices. It can go out to the internet and fetch metadata for your books. It can download newspapers and convert them into e-books for convenient reading.'%__appname__,
    '-DPackageSummary', '%s: E-book library management'%__appname__,
    '-DVersion', __version__,
    '-DInstallVersion', sv + '.0',
    '-DLicense', open(os.path.join(os.path.dirname(SRC), 'LICENSE'), 'rb').read().replace('\n', '\r\n'),
    '--output-dir', os.path.join(os.path.dirname(SRC), 'dist'),
    '--platform', 'Windows',
    '--verbose'
]

def run_install_jammer(installer_name='<%AppName%>-<%Version%><%Ext%>', build_for_release=True):
    global cmdline
    mpi = os.path.abspath(os.path.join(os.path.dirname(__file__), 'calibre', 'calibre.mpi'))
    cmdline.extend(['-DWindows,Executable', installer_name])
    compression = 'zlib'
    if build_for_release:
        cmdline += ['--build-for-release']
        compression = 'lzma (solid)'
    cmdline += ['-DCompressionMethod', compression]
    cmdline += ['--build', mpi]
    #print 'Running installjammer with cmdline:'
    #print cmdline
    subprocess.check_call(cmdline)

def main(args=sys.argv):
    run_install_jammer(build_for_release=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
