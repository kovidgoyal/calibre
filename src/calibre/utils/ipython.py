#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, sys
from calibre.constants import iswindows, cache_dir, get_version

ipydir = os.path.join(cache_dir(), 'ipython')

BANNER = ('Welcome to the interactive calibre shell!\n')


def setup_pyreadline():
    config = '''
#Bind keys for exit (keys only work on empty lines
#disable_readline(True)		#Disable pyreadline completely.
from __future__ import print_function, unicode_literals, absolute_import
debug_output("off")             #"on" saves log info to./pyreadline_debug_log.txt
                                #"on_nologfile" only enables print warning messages
bind_exit_key("Control-d")
bind_exit_key("Control-z")

#Commands for moving
bind_key("Home",                "beginning_of_line")
bind_key("End",                 "end_of_line")
bind_key("Left",                "backward_char")
bind_key("Control-b",           "backward_char")
bind_key("Right",               "forward_char")
bind_key("Control-f",           "forward_char")
bind_key("Alt-f",               "forward_word")
bind_key("Alt-b",               "backward_word")
bind_key("Clear",               "clear_screen")
bind_key("Control-l",           "clear_screen")
bind_key("Control-a",           "beginning_of_line")
bind_key("Control-e",           "end_of_line")
#bind_key("Control-l",          "redraw_current_line")

#Commands for Manipulating the History
bind_key("Return",              "accept_line")
bind_key("Control-p",           "previous_history")
bind_key("Control-n",           "next_history")
bind_key("Up",                  "history_search_backward")
bind_key("Down",                "history_search_forward")
bind_key("Alt-<",               "beginning_of_history")
bind_key("Alt->",               "end_of_history")
bind_key("Control-r",           "reverse_search_history")
bind_key("Control-s",           "forward_search_history")
bind_key("Alt-p",               "non_incremental_reverse_search_history")
bind_key("Alt-n",               "non_incremental_forward_search_history")

bind_key("Control-z",           "undo")
bind_key("Control-_",           "undo")

#Commands for Changing Text
bind_key("Delete",              "delete_char")
bind_key("Control-d",           "delete_char")
bind_key("BackSpace",           "backward_delete_char")
#bind_key("Control-Shift-v",    "quoted_insert")
bind_key("Control-space",       "self_insert")
bind_key("Control-BackSpace",   "backward_delete_word")

#Killing and Yanking
bind_key("Control-k",           "kill_line")
bind_key("Control-shift-k",     "kill_whole_line")
bind_key("Escape",              "kill_whole_line")
bind_key("Meta-d",              "kill_word")
bind_key("Control-w",           "unix_word_rubout")
#bind_key("Control-Delete",     "forward_kill_word")

#Copy paste
bind_key("Shift-Right",         "forward_char_extend_selection")
bind_key("Shift-Left",          "backward_char_extend_selection")
bind_key("Shift-Control-Right", "forward_word_extend_selection")
bind_key("Shift-Control-Left",  "backward_word_extend_selection")
bind_key("Control-m",           "set_mark")

bind_key("Control-Shift-x",     "copy_selection_to_clipboard")
#bind_key("Control-c",           "copy_selection_to_clipboard")  #Needs allow_ctrl_c(True) below to be uncommented
bind_key("Control-q",           "copy_region_to_clipboard")
bind_key('Control-Shift-v',     "paste_mulitline_code")
bind_key("Control-x",           "cut_selection_to_clipboard")

bind_key("Control-v",           "paste")
bind_key("Control-y",           "yank")
bind_key("Alt-v",               "ipython_paste")

#Unbinding keys:
#un_bind_key("Home")

#Other
bell_style("none") #modes: none, audible, visible(not implemented)
show_all_if_ambiguous("on")
mark_directories("on")
completer_delims(" \t\n\"\\'`@$><=;|&{(?")
complete_filesystem("on")
debug_output("off")
#allow_ctrl_c(True)  #(Allows use of ctrl-c as copy key, still propagate keyboardinterrupt when not waiting for input)

history_filename(%r)
history_length(2000) #value of -1 means no limit

#set_mode("vi")  #will cause following bind_keys to bind to vi mode as well as activate vi mode
#ctrl_c_tap_time_interval(0.3)
    '''
    try:
        import pyreadline.rlmain
        if not os.path.exists(ipydir):
            os.makedirs(ipydir)
        conf = os.path.join(ipydir, 'pyreadline.txt')
        hist = os.path.join(ipydir, 'history.txt')
        config = config % hist
        with open(conf, 'wb') as f:
            f.write(config.encode('utf-8'))
        pyreadline.rlmain.config_path = conf
        import readline, atexit
        import pyreadline.unicode_helper  # noqa
        # Normally the codepage for pyreadline is set to be sys.stdout.encoding
        # if you need to change this uncomment the following line
        # pyreadline.unicode_helper.pyreadline_codepage="utf8"
    except ImportError:
        print("Module readline not available.")
    else:
        # import tab completion functionality
        import rlcompleter

        # Override completer from rlcompleter to disable automatic ( on callable
        completer_obj = rlcompleter.Completer()

        def nop(val, word):
            return word
        completer_obj._callable_postfix = nop
        readline.set_completer(completer_obj.complete)

        # activate tab completion
        readline.parse_and_bind("tab: complete")
        readline.read_history_file()
        atexit.register(readline.write_history_file)
        del readline, rlcompleter, atexit


def simple_repl(user_ns={}):
    if iswindows:
        setup_pyreadline()
    else:
        try:
            import rlcompleter  # noqa
            import readline  # noqa
            readline.parse_and_bind("tab: complete")
        except ImportError:
            pass

    user_ns = user_ns or {}
    import sys, re  # noqa
    for x in ('os', 'sys', 're'):
        user_ns[x] = user_ns.get(x, globals().get(x, locals().get(x)))
    import code
    code.interact(BANNER, raw_input, user_ns)


def ipython(user_ns=None):
    os.environ['IPYTHONDIR'] = ipydir
    try:
        from IPython.terminal.embed import InteractiveShellEmbed
        from traitlets.config.loader import Config
        from IPython.terminal.prompts import Prompts, Token
    except ImportError:
        return simple_repl(user_ns=user_ns)

    class CustomPrompt(Prompts):

        def in_prompt_tokens(self, cli=None):
            return [
                (Token.Prompt, 'calibre['),
                (Token.PromptNum, get_version()),
                (Token.Prompt, ']> '),
            ]

        def out_prompt_tokens(self):
            return []

    defns = {'os':os, 're':re, 'sys':sys}
    defns.update(user_ns or {})

    c = Config()
    user_conf = os.path.expanduser('~/.ipython/profile_default/ipython_config.py')
    if os.path.exists(user_conf):
        execfile(user_conf, {'get_config': lambda: c})
    c.TerminalInteractiveShell.prompts_class = CustomPrompt
    c.InteractiveShellApp.exec_lines = [
        'from __future__ import division, absolute_import, unicode_literals, print_function',
        ]
    c.TerminalInteractiveShell.confirm_exit = False
    c.TerminalInteractiveShell.banner1 = BANNER
    c.BaseIPythonApplication.ipython_dir = ipydir

    c.InteractiveShell.separate_in = ''
    c.InteractiveShell.separate_out = ''
    c.InteractiveShell.separate_out2 = ''

    ipshell = InteractiveShellEmbed.instance(config=c, user_ns=user_ns)
    ipshell()
