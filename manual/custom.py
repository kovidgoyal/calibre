#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import sys, os, re, textwrap

sys.path.insert(0, os.path.abspath('../src'))
sys.extensions_location = '../src/calibre/plugins'
sys.resources_location  = '../resources'

from sphinx.util.console import bold

sys.path.append(os.path.abspath('../../../'))
from calibre.linux import entry_points
from epub import EPUBHelpBuilder

def substitute(app, doctree):
    pass

CLI_INDEX='''
.. include:: ../global.rst

.. _cli:

Command Line Interface
==========================

.. image:: ../images/cli.png

On OS X you have to go to Preferences->Advanced->Miscellaneous and click install command line
tools to make the command line tools available.  On other platforms, just start
a terminal and type the command.

Documented Commands
--------------------

.. toctree::
    :maxdepth: 1

{documented}

Undocumented Commands
-------------------------

{undocumented}

You can see usage for undocumented commands by executing them without arguments
in a terminal.
'''

CLI_PREAMBLE='''\
.. include:: ../global.rst

.. _{cmd}:

{cmd}
===================================================================

.. code-block:: none

    {cmdline}

{usage}
'''

def generate_calibredb_help(preamble, info):
    from calibre.library.cli import COMMANDS, get_parser
    import calibre.library.cli as cli
    preamble = preamble[:preamble.find('\n\n\n', preamble.find('code-block'))]
    preamble += textwrap.dedent('''

    :command:`calibredb` is the command line interface to the |app| database. It has
    several sub-commands, documented below:

    ''')

    global_parser = get_parser('')
    groups = []
    for grp in global_parser.option_groups:
        groups.append((grp.title.capitalize(), grp.description, grp.option_list))

    global_options = '\n'.join(render_options('calibredb', groups, False, False))


    lines, toc = [], []
    for cmd in COMMANDS:
        args = []
        if cmd == 'catalog':
            args = [['doc.xml', '-h']]
        parser = getattr(cli, cmd+'_option_parser')(*args)
        if cmd == 'catalog':
            parser = parser[0]
        toc.append('  * :ref:`calibredb-%s`'%cmd)
        lines += ['.. _calibredb-'+cmd+':', '']
        lines += [cmd, '~'*20, '']
        usage = parser.usage.strip()
        usage = [i for i in usage.replace('%prog', 'calibredb').splitlines()]
        cmdline = '    '+usage[0]
        usage = usage[1:]
        usage = [i.replace(cmd, ':command:`%s`'%cmd) for i in usage]
        lines += ['.. code-block:: none', '', cmdline, '']
        lines += usage
        groups = [(None, None, parser.option_list)]
        lines += ['']
        lines += render_options('calibredb '+cmd, groups, False)
        lines += ['']

    toc = '\n'.join(toc)
    raw = preamble + '\n\n'+toc + '\n\n' + global_options+'\n\n'+'\n'.join(lines)
    update_cli_doc(os.path.join('cli', 'calibredb.rst'), raw, info)

def generate_ebook_convert_help(preamble, info):
    from calibre.ebooks.conversion.cli import create_option_parser
    from calibre.customize.ui import input_format_plugins, output_format_plugins
    from calibre.utils.logging import default_log
    preamble = re.sub(r'http.*\.html', ':ref:`conversion`', preamble)
    raw = preamble + textwrap.dedent('''
    The options and default values for the options change depending on both the
    input and output formats, so you should always check with::

        ebook-convert myfile.input_format myfile.output_format -h

    Below are the options that are common to all conversion, followed by the
    options specific to every input and output format

    ''')
    parser, plumber = create_option_parser(['ebook-convert',
        'dummyi.mobi', 'dummyo.epub', '-h'], default_log)
    groups = [(None, None, parser.option_list)]
    for grp in parser.option_groups:
        if grp.title not in {'INPUT OPTIONS', 'OUTPUT OPTIONS'}:
            groups.append((grp.title.title(), grp.description, grp.option_list))
    options = '\n'.join(render_options('ebook-convert', groups, False))

    raw += '\n\n.. contents::\n  :local:'

    raw += '\n\n' + options
    for pl in sorted(input_format_plugins(), key=lambda x:x.name):
        parser, plumber = create_option_parser(['ebook-convert',
            'dummyi.'+list(pl.file_types)[0], 'dummyo.epub', '-h'], default_log)
        groups = [(pl.name+ ' Options', '', g.option_list) for g in
                parser.option_groups if g.title == "INPUT OPTIONS"]
        prog = 'ebook-convert-'+(pl.name.lower().replace(' ', '-'))
        raw += '\n\n' + '\n'.join(render_options(prog, groups, False, True))
    for pl in sorted(output_format_plugins(), key=lambda x: x.name):
        parser, plumber = create_option_parser(['ebook-convert', 'd.epub',
            'dummyi.'+pl.file_type, '-h'], default_log)
        groups = [(pl.name+ ' Options', '', g.option_list) for g in
                parser.option_groups if g.title == "OUTPUT OPTIONS"]
        prog = 'ebook-convert-'+(pl.name.lower().replace(' ', '-'))
        raw += '\n\n' + '\n'.join(render_options(prog, groups, False, True))


    update_cli_doc(os.path.join('cli', 'ebook-convert.rst'), raw, info)

def update_cli_doc(path, raw, info):
    if isinstance(raw, unicode):
        raw = raw.encode('utf-8')
    old_raw = open(path, 'rb').read() if os.path.exists(path) else ''
    if not os.path.exists(path) or old_raw != raw:
        import difflib
        print path, 'has changed'
        if old_raw:
            lines = difflib.unified_diff(old_raw.splitlines(), raw.splitlines(),
                    path, path)
            for line in lines:
                print line
        info('creating '+os.path.splitext(os.path.basename(path))[0])
        open(path, 'wb').write(raw)

def render_options(cmd, groups, options_header=True, add_program=True):
    lines = ['']
    if options_header:
        lines = ['[options]', '-'*15, '']
    if add_program:
        lines += ['.. program:: '+cmd, '']
    for title, desc, options in groups:
        if title:
            lines.extend([title, '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'])
            lines.append('')
        if desc:
            lines.extend([desc, ''])
        for opt in sorted(options, cmp=lambda x, y:cmp(x.get_opt_string(),
                y.get_opt_string())):
            help = opt.help if opt.help else ''
            help = help.replace('\n', ' ').replace('*', '\\*').replace('%default', str(opt.default))
            opt = opt.get_opt_string() + ((', '+', '.join(opt._short_opts)) if opt._short_opts else '')
            opt = '.. cmdoption:: '+opt
            lines.extend([opt, '', '    '+help, ''])
    return lines

def cli_docs(app):
    info = app.builder.info
    info(bold('creating CLI documentation...'))
    documented_cmds = []
    undocumented_cmds = []

    for script in entry_points['console_scripts'] + entry_points['gui_scripts']:
        module = script[script.index('=')+1:script.index(':')].strip()
        cmd = script[:script.index('=')].strip()
        if cmd in ('calibre-complete', 'calibre-parallel'): continue
        module = __import__(module, fromlist=[module.split('.')[-1]])
        if hasattr(module, 'option_parser'):
            documented_cmds.append((cmd, getattr(module, 'option_parser')()))
        else:
            undocumented_cmds.append(cmd)

    documented_cmds.sort(cmp=lambda x, y: cmp(x[0], y[0]))
    undocumented_cmds.sort()

    documented = [' '*4 + cmd[0] for cmd in documented_cmds]
    undocumented = ['  * ' + cmd for cmd in undocumented_cmds]

    raw = CLI_INDEX.format(documented='\n'.join(documented),
            undocumented='\n'.join(undocumented))
    if not os.path.exists('cli'):
        os.makedirs('cli')
    update_cli_doc(os.path.join('cli', 'cli-index.rst'), raw, info)

    for cmd, parser in documented_cmds:
        usage = [i for i in parser.usage.replace('%prog', cmd).splitlines()]
        cmdline = usage[0]
        usage = usage[1:]
        usage = [i.replace(cmd, ':command:`%s`'%cmd) for i in usage]
        usage = '\n'.join(usage)
        preamble = CLI_PREAMBLE.format(cmd=cmd, cmdline=cmdline, usage=usage)
        if cmd == 'ebook-convert':
            generate_ebook_convert_help(preamble, info)
        elif cmd == 'calibredb':
            generate_calibredb_help(preamble, info)
        else:
            groups = [(None, None, parser.option_list)]
            for grp in parser.option_groups:
                groups.append((grp.title, grp.description, grp.option_list))
            raw = preamble
            lines = render_options(cmd, groups)
            raw += '\n'+'\n'.join(lines)
            update_cli_doc(os.path.join('cli', cmd+'.rst'), raw, info)

def generate_docs(app):
    cli_docs(app)
    template_docs(app)

def template_docs(app):
    from template_ref_generate import generate_template_language_help
    info = app.builder.info
    raw = generate_template_language_help()
    update_cli_doc('template_ref.rst', raw, info)

def setup(app):
    app.add_config_value('kovid_epub_cover', None, False)
    app.add_builder(EPUBHelpBuilder)
    app.connect('doctree-read', substitute)
    app.connect('builder-inited', generate_docs)
    app.connect('build-finished', finished)

def finished(app, exception):
    pass

