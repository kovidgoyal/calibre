from __future__ import with_statement
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Command line interface to run pdf manipulation commands.
'''

import string, sys

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.ebooks.pdf.manipulate import crop, decrypt, encrypt, \
    info, merge, reverse, rotate, split

COMMANDS = {
             'crop'    : crop,
             'decrypt' : decrypt,
             'encrypt' : encrypt,
             'info'    : info,
             'merge'   : merge,
             'reverse' : reverse,
             'rotate'  : rotate,
             'split'   : split,
           }

USAGE = '%prog ' + _('''command ...

command can be one of the following:
[%%commands]

Use %prog command --help to get more information about a specific command

Manipulate a PDF.
''').replace('%%commands', string.join(sorted(COMMANDS.keys()), ', '))

def print_help(parser, log):
    help = parser.format_help().encode(preferred_encoding, 'replace')
    log(help)

def option_parser():
    return OptionParser(usage=USAGE)

def main(args=sys.argv):
    log = Log()
    parser = option_parser()

    if len(args) < 2:
        print 'Error: No command sepecified.\n'
        print_help(parser, log)
        return 1

    command = args[1].lower().strip()

    if command in COMMANDS.keys():
        del args[1]
        return COMMANDS[command].main(args, command)
    else:
        parser.parse_args(args)
        print 'Unknown command %s.\n' % command
        print_help(parser, log)
        return 1

    # We should never get here.
    return 0

if __name__ == '__main__':
    sys.exit(main())
