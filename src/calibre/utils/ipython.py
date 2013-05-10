#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from calibre.constants import iswindows, cache_dir, get_version

ipydir = os.path.join(cache_dir(), 'ipython')

BANNER = ('Welcome to the interactive calibre shell!\n')

def setup_pyreadline():
    try:
        import pyreadline.rlmain
        #pyreadline.rlmain.config_path=r"c:\xxx\pyreadlineconfig.ini"
        import readline, atexit
        import pyreadline.unicode_helper  # noqa
        #Normally the codepage for pyreadline is set to be sys.stdout.encoding
        #if you need to change this uncomment the following line
        #pyreadline.unicode_helper.pyreadline_codepage="utf8"
    except ImportError:
        print("Module readline not available.")
    else:
        #import tab completion functionality
        import rlcompleter

        #Override completer from rlcompleter to disable automatic ( on callable
        completer_obj = rlcompleter.Completer()
        def nop(val, word):
            return word
        completer_obj._callable_postfix = nop
        readline.set_completer(completer_obj.complete)

        #activate tab completion
        readline.parse_and_bind("tab: complete")
        readline.read_history_file()
        atexit.register(readline.write_history_file)
        del readline, rlcompleter, atexit

def simple_repl(user_ns={}):
    if iswindows:
        setup_pyreadline()
    else:
        try:
            import readline  # noqa
        except ImportError:
            pass

    import code
    code.interact(BANNER, raw_input, user_ns)

def ipython(user_ns=None):
    try:
        import IPython
        from IPython.config.loader import Config
    except ImportError:
        return simple_repl(user_ns=user_ns)
    if not user_ns:
        user_ns = {}
    c = Config()
    c.InteractiveShellApp.exec_lines = [
        'from __future__ import division, absolute_import, unicode_literals, print_function',
        ]
    c.TerminalInteractiveShell.confirm_exit = False
    c.PromptManager.in_template = (r'{color.LightGreen}calibre '
            '{color.LightBlue}[{color.LightCyan}%s{color.LightBlue}]'
            r'{color.Green}|\#> '%get_version())
    c.PromptManager.in2_template = r'{color.Green}|{color.LightGreen}\D{color.Green}> '
    c.PromptManager.out_template = r'<\#> '
    c.TerminalInteractiveShell.banner1 = BANNER
    c.PromptManager.justify = True
    c.TerminalIPythonApp.ipython_dir = ipydir
    os.environ['IPYTHONDIR'] = ipydir

    c.InteractiveShell.separate_in = ''
    c.InteractiveShell.separate_out = ''
    c.InteractiveShell.separate_out2 = ''

    c.PrefilterManager.multi_line_specials = True

    IPython.embed(config=c, user_ns=user_ns)

