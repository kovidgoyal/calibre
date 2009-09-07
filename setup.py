#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import sys, os, optparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import setup.commands as commands
from setup import prints, get_warnings

def check_version_info():
    vi = sys.version_info
    if vi[0] == 2 and vi[1] > 5:
        return None
    return 'calibre requires python >= 2.6'

def option_parser():
    parser = optparse.OptionParser()
    return parser

def main(args=sys.argv):
    if len(args) == 1 or args[1] in ('-h', '--help'):
        print 'Usage: python', args[0], 'command', '[options]'
        print '\nWhere command is one of:', ', '.join(commands.__all__)
        print '\nTo get help on a particular command, run:'
        print '\tpython', args[0], 'command -h'
        return 1

    command = args[1]
    if command not in commands.__all__:
        print command, 'is not a recognized command.'
        print 'Valid commands:', ', '.join(commands.__all__)
        return 1

    command = getattr(commands, command)

    parser = option_parser()
    command.add_all_options(parser)
    parser.set_usage('Usage: python setup.py %s [options]\n\n'%args[1]+\
            command.description)

    opts, args = parser.parse_args(args)
    command.run_all(opts)

    warnings = get_warnings()
    if warnings:
        print
        prints('There were', len(warnings), 'warning(s):')
        print
        for args, kwargs in warnings:
            prints(*args, **kwargs)
            print

    return 0

if __name__ == '__main__':
    sys.exit(main())
