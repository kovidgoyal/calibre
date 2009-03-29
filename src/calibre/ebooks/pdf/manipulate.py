'''
Command line interface to run pdf manipulation commands.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import string, sys

from calibre.utils.config import Config, StringConfig
from calibre.ebooks.pdf import info, merge, split, trim

COMMANDS = {
             'info'  : info,
             'merge' : merge,
             'split' : split,
             'trim'  : trim,
           }

def config(defaults=None):
    desc = _('Options to control the transformation of pdf')
    if defaults is None:
        c = Config('manipulatepdf', desc)
    else:
        c = StringConfig(defaults, desc)
    return c

def option_parser():
    c = config()
    return c.option_parser(usage=_('''\
    
	%prog command ...
	
	command can be one of the following:
	[%%commands]
	
	Use %prog command --help to get more information about a specific command
	
	Manipulate a PDF.
	'''.replace('%%commands', string.join(sorted(COMMANDS.keys()), ', '))))

def main(args=sys.argv):
    parser = option_parser()

    if len(args) < 2:
        print 'Error: No command sepecified.\n'
        print parser.get_usage()
        return 2
    
    command = args[1].lower().strip()
    
    if command in COMMANDS.keys():    
        del args[1]
        return COMMANDS[command].main(args, command)
    else:
        parser.parse_args(args)
        print 'Unknown command %s.\n' % command
        print parser.get_usage()
        return 2
    
    # We should never get here.
    return 0

if __name__ == '__main__':
    sys.exit(main())

