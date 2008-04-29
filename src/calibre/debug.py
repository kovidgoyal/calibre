#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Embedded console for debugging.
'''

import sys

def main(args=sys.argv):
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed()
    ipshell()

    return 0

if __name__ == '__main__':
    sys.exit(main())