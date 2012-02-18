#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os
from calibre.constants import iswindows, config_dir, get_version

ipydir = os.path.join(config_dir, ('_' if iswindows else '.')+'ipython')

def old_ipython(user_ns=None): # {{{
    old_argv = sys.argv
    sys.argv = ['ipython']
    if user_ns is None:
        user_ns = locals()
    os.environ['IPYTHONDIR'] = ipydir
    if not os.path.exists(ipydir):
        os.makedirs(ipydir)
    for x in ('', '.ini'):
        rc = os.path.join(ipydir, 'ipythonrc'+x)
        if not os.path.exists(rc):
            open(rc, 'wb').write(' ')
    UC = '''
import IPython.ipapi
ip = IPython.ipapi.get()

# You probably want to uncomment this if you did %upgrade -nolegacy
import ipy_defaults

import os, re, sys

def main():
    # Handy tab-completers for %cd, %run, import etc.
    # Try commenting this out if you have completion problems/slowness
    import ipy_stock_completers

    # uncomment if you want to get ipython -p sh behaviour
    # without having to use command line switches

    import ipy_profile_sh


    # Configure your favourite editor?
    # Good idea e.g. for %edit os.path.isfile

    import ipy_editors

    # Choose one of these:

    #ipy_editors.scite()
    #ipy_editors.scite('c:/opt/scite/scite.exe')
    #ipy_editors.komodo()
    #ipy_editors.idle()
    # ... or many others, try 'ipy_editors??' after import to see them

    # Or roll your own:
    #ipy_editors.install_editor("c:/opt/jed +$line $file")

    ipy_editors.kate()

    o = ip.options
    # An example on how to set options
    #o.autocall = 1
    o.system_verbose = 0
    o.confirm_exit = 0

main()
    '''
    uc = os.path.join(ipydir, 'ipy_user_conf.py')
    if not os.path.exists(uc):
        open(uc, 'wb').write(UC)
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed(user_ns=user_ns)
    ipshell()
    sys.argv = old_argv
# }}}

def ipython(user_ns=None):
    try:
        import IPython
        from IPython.config.loader import Config
    except ImportError:
        return old_ipython(user_ns=user_ns)
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
    c.TerminalInteractiveShell.banner1 = ('Welcome to the interactive calibre'
            ' shell!\n\n')
    c.PromptManager.justify = True
    c.TerminalIPythonApp.ipython_dir = ipydir
    os.environ['IPYTHONDIR'] = ipydir

    c.InteractiveShell.separate_in = ''
    c.InteractiveShell.separate_out = ''
    c.InteractiveShell.separate_out2 = ''

    c.PrefilterManager.multi_line_specials = True

    IPython.embed(config=c, user_ns=user_ns)

