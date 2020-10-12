#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__ = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os


def check_version_info():
    vi = sys.version_info
    if vi.major > 3 or (vi.major == 3 and vi[1:3] >= (7, 0)):
        return
    raise SystemExit(
        'calibre requires python >= 3.7.0. Current python version: ' + '.'.join(map(str, vi[:3])))


check_version_info()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import setup.commands as commands
from setup import prints, get_warnings


def option_parser():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option(
        '-c',
        '--clean',
        default=False,
        action='store_true',
        help=('Instead of running the command delete all files generated '
              'by the command'))
    parser.add_option(
        '--clean-backups',
        default=False,
        action='store_true',
        help='Delete all backup files from the source tree')
    parser.add_option(
        '--clean-all',
        default=False,
        action='store_true',
        help='Delete all machine generated files from the source tree')
    return parser


def clean_backups():
    for root, _, files in os.walk('.'):
        for name in files:
            for t in ('.pyc', '.pyo', '~', '.swp', '.swo'):
                if name.endswith(t):
                    os.remove(os.path.join(root, name))


def main(args=sys.argv):
    if len(args) == 1 or args[1] in ('-h', '--help'):
        print('Usage: python', args[0], 'command', '[options]')
        print('\nWhere command is one of:')
        print()
        for x in sorted(commands.__all__):
            print('{:20} -'.format(x), end=' ')
            c = getattr(commands, x)
            desc = getattr(c, 'short_description', c.description)
            print(desc)

        print('\nTo get help on a particular command, run:')
        print('\tpython', args[0], 'command -h')
        return 1

    command = args[1]
    if command not in commands.__all__:
        print(command, 'is not a recognized command.')
        print('Valid commands:', ', '.join(commands.__all__))
        return 1

    command = getattr(commands, command)

    parser = option_parser()
    command.add_all_options(parser)
    parser.set_usage(
        'Usage: python setup.py {} [options]\n\n'.format(args[1]) + command.description)

    opts, args = parser.parse_args(args)
    opts.cli_args = args[2:]

    if opts.clean_backups:
        clean_backups()

    if opts.clean:
        prints('Cleaning', args[1])
        command.clean()
        return 0

    if opts.clean_all:
        for cmd in commands.__all__:
            prints('Cleaning', cmd)
            getattr(commands, cmd).clean()
        return 0

    command.run_all(opts)

    warnings = get_warnings()
    if warnings:
        print()
        prints('There were', len(warnings), 'warning(s):')
        print()
        for args, kwargs in warnings:
            prints('*', *args, **kwargs)
            print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
