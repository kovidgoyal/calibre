#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import sys, os, re, textwrap
from functools import partial
import init_calibre
del init_calibre

from sphinx.util.console import bold

sys.path.append(os.path.abspath('../../../'))
from calibre.linux import entry_points, cli_index_strings
from epub import EPUBHelpBuilder
from latex import LaTeXHelpBuilder


def substitute(app, doctree):
    pass


include_pat = re.compile(r'^.. include:: (\S+.rst)', re.M)


def source_read_handler(app, docname, source):
    src = source[0]
    if app.builder.name != 'gettext' and app.config.language != 'en':
        src = re.sub(r'(\s+generated/)en/', r'\1' + app.config.language + '/', src)
    # Sphinx does not call source_read_handle for the .. include directive
    for m in reversed(tuple(include_pat.finditer(src))):
        included_doc_name = m.group(1).lstrip('/')
        ss = [open(included_doc_name).read().decode('utf-8')]
        source_read_handler(app, included_doc_name.partition('.')[0], ss)
        src = src[:m.start()] + ss[0] + src[m.end():]
    source[0] = src


CLI_INDEX='''
.. _cli:

%s
=========================================================

.. image:: ../../images/cli.png

.. note::
    %s

%s
--------------------------------------

.. toctree::
    :maxdepth: 1

{documented}

%s
----------------------------------------

{undocumented}

%s
'''

CLI_PREAMBLE='''\
.. _{cmdref}:

``{cmd}``
===================================================================

.. code-block:: none

    {cmdline}

{usage}
'''


def titlecase(app, x):
    if x and app.config.language == 'en':
        from calibre.utils.titlecase import titlecase as tc
        x = tc(x)
    return x


def generate_calibredb_help(preamble, app):
    from calibre.db.cli.main import COMMANDS, option_parser_for, get_parser
    preamble = preamble[:preamble.find('\n\n\n', preamble.find('code-block'))]
    preamble += textwrap.dedent('''

    :command:`calibredb` is the command line interface to the calibre database. It has
    several sub-commands, documented below.

    :command:`calibredb` can be used to manipulate either a calibre database
    specified by path or a calibre :guilabel:`Content server` running either on
    the local machine or over the internet. You can start a calibre
    :guilabel:`Content server` using either the :command:`calibre-server`
    program or in the main calibre program click :guilabel:`Connect/share ->
    Start Content server`. Since :command:`calibredb` can make changes to your
    calibre libraries, you must setup authentication on the server first. There
    are two ways to do that:

        * If you plan to connect only to a server running on the same computer,
          you can simply use the ``--enable-local-write`` option of the
          content server, to allow any program, including calibredb, running on
          the local computer to make changes to your calibre data. When running
          the server from the main calibre program, this option is in
          :guilabel:`Preferences->Sharing over the net->Advanced`.

        * If you want to enable access over the internet, then you should setup
          user accounts on the server and use the :option:`--username` and :option:`--password`
          options to :command:`calibredb` to give it access. You can setup
          user authentication for :command:`calibre-server` by using the ``--enable-auth``
          option and using ``--manage-users`` to create the user accounts.
          If you are running the server from the main calibre program, use
          :guilabel:`Preferences->Sharing over the net->Require username/password`.


    ''')

    global_parser = get_parser('')
    groups = []
    for grp in global_parser.option_groups:
        groups.append((titlecase(app, grp.title), grp.description, grp.option_list))

    global_options = '\n'.join(render_options('calibredb', groups, False, False))

    lines = []
    for cmd in COMMANDS:
        parser = option_parser_for(cmd)()
        lines += ['.. _calibredb-%s-%s:' % (app.config.language, cmd), '']
        lines += [cmd, '~'*20, '']
        usage = parser.usage.strip()
        usage = [i for i in usage.replace('%prog', 'calibredb').splitlines()]
        cmdline = '    '+usage[0]
        usage = usage[1:]
        usage = [re.sub(r'(%s)([^a-zA-Z0-9])'%cmd, r':command:`\1`\2', i) for i in usage]
        lines += ['.. code-block:: none', '', cmdline, '']
        lines += usage
        groups = [(None, None, parser.option_list)]
        lines += ['']
        lines += render_options('calibredb '+cmd, groups, False)
        lines += ['']
        for group in parser.option_groups:
            if not getattr(group, 'is_global_options', False):
                lines.extend(render_options(
                    'calibredb_' + cmd, [[titlecase(app, group.title), group.description, group.option_list]], False, False, header_level='^'))
        lines += ['']

    raw = preamble + '\n\n'+'.. contents::\n  :local:'+ '\n\n' + global_options+'\n\n'+'\n'.join(lines)
    update_cli_doc('calibredb', raw, app)


def generate_ebook_convert_help(preamble, app):
    from calibre.ebooks.conversion.cli import create_option_parser, manual_index_strings
    from calibre.customize.ui import input_format_plugins, output_format_plugins
    from calibre.utils.logging import default_log
    preamble = re.sub(r'http.*\.html', ':ref:`conversion`', preamble)

    raw = preamble + '\n\n' + manual_index_strings() % 'ebook-convert myfile.input_format myfile.output_format -h'
    parser, plumber = create_option_parser(['ebook-convert',
        'dummyi.mobi', 'dummyo.epub', '-h'], default_log)
    groups = [(None, None, parser.option_list)]
    for grp in parser.option_groups:
        if grp.title not in {'INPUT OPTIONS', 'OUTPUT OPTIONS'}:
            groups.append((titlecase(app, grp.title), grp.description, grp.option_list))
    options = '\n'.join(render_options('ebook-convert', groups, False))

    raw += '\n\n.. contents::\n  :local:'

    raw += '\n\n' + options
    for pl in sorted(input_format_plugins(), key=lambda x:x.name):
        parser, plumber = create_option_parser(['ebook-convert',
            'dummyi.'+sorted(pl.file_types)[0], 'dummyo.epub', '-h'], default_log)
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

    update_cli_doc('ebook-convert', raw, app)


def update_cli_doc(name, raw, app):
    if isinstance(raw, unicode):
        raw = raw.encode('utf-8')
    path = 'generated/%s/%s.rst' % (app.config.language, name)
    old_raw = open(path, 'rb').read() if os.path.exists(path) else ''
    if not os.path.exists(path) or old_raw != raw:
        import difflib
        print path, 'has changed'
        if old_raw:
            lines = difflib.unified_diff(old_raw.splitlines(), raw.splitlines(),
                    path, path)
            for line in lines:
                print line
        app.builder.info('creating '+os.path.splitext(os.path.basename(path))[0])
        p = os.path.dirname(path)
        if p and not os.path.exists(p):
            os.makedirs(p)
        open(path, 'wb').write(raw)


def render_options(cmd, groups, options_header=True, add_program=True, header_level='~'):
    lines = ['']
    if options_header:
        lines = [_('[options]'), '-'*40, '']
    if add_program:
        lines += ['.. program:: '+cmd, '']
    for title, desc, options in groups:
        if title:
            lines.extend([title, header_level * (len(title) + 4)])
            lines.append('')
        if desc:
            lines.extend([desc, ''])
        for opt in sorted(options, key=lambda x: x.get_opt_string()):
            help = opt.help or ''
            help = help.replace('\n', ' ').replace('*', '\\*').replace('%default', str(opt.default))
            help = help.replace('"', r'\ ``"``\ ')
            help = help.replace("'", r"\ ``'``\ ")
            help = mark_options(help)
            opt_strings = (x.strip() for x in tuple(opt._long_opts or ()) + tuple(opt._short_opts or ()))
            opt = '.. option:: ' + ', '.join(opt_strings)
            lines.extend([opt, '', '    '+help, ''])
    return lines


def mark_options(raw):
    raw = re.sub(r'(\s+)--(\s+)', ur'\1-\u200b-\2', raw)

    def sub(m):
        opt = m.group()
        a, b = opt.partition('=')[::2]
        if a in ('--option1', '--option2'):
            return '``' + m.group() + '``'
        a = ':option:`' + a + '`'
        b = (' = ``' + b + '``') if b else ''
        return a + b
    raw = re.sub(r'(--[|()a-zA-Z0-9_=,-]+)', sub, raw)
    return raw


def cli_docs(app):
    info = app.builder.info
    info(bold('creating CLI documentation...'))
    documented_cmds = []
    undocumented_cmds = []

    for script in entry_points['console_scripts'] + entry_points['gui_scripts']:
        module = script[script.index('=')+1:script.index(':')].strip()
        cmd = script[:script.index('=')].strip()
        if cmd in ('calibre-complete', 'calibre-parallel'):
            continue
        module = __import__(module, fromlist=[module.split('.')[-1]])
        if hasattr(module, 'option_parser'):
            try:
                documented_cmds.append((cmd, getattr(module, 'option_parser')()))
            except TypeError:
                documented_cmds.append((cmd, getattr(module, 'option_parser')(cmd)))
        else:
            undocumented_cmds.append(cmd)

    documented_cmds.sort(cmp=lambda x, y: cmp(x[0], y[0]))
    undocumented_cmds.sort()

    documented = [' '*4 + c[0] for c in documented_cmds]
    undocumented = ['  * ' + c for c in undocumented_cmds]

    raw = (CLI_INDEX % cli_index_strings()[:5]).format(documented='\n'.join(documented),
            undocumented='\n'.join(undocumented))
    if not os.path.exists('cli'):
        os.makedirs('cli')
    update_cli_doc('cli-index', raw, app)

    for cmd, parser in documented_cmds:
        usage = [mark_options(i) for i in parser.usage.replace('%prog', cmd).splitlines()]
        cmdline = usage[0]
        usage = usage[1:]
        usage = [i.replace(cmd, ':command:`%s`'%cmd) for i in usage]
        usage = '\n'.join(usage)
        preamble = CLI_PREAMBLE.format(cmd=cmd, cmdref=cmd + '-' + app.config.language, cmdline=cmdline, usage=usage)
        if cmd == 'ebook-convert':
            generate_ebook_convert_help(preamble, app)
        elif cmd == 'calibredb':
            generate_calibredb_help(preamble, app)
        else:
            groups = [(None, None, parser.option_list)]
            for grp in parser.option_groups:
                groups.append((grp.title, grp.description, grp.option_list))
            raw = preamble
            lines = render_options(cmd, groups)
            raw += '\n'+'\n'.join(lines)
            update_cli_doc(cmd, raw, app)


def generate_docs(app):
    cli_docs(app)
    template_docs(app)


def template_docs(app):
    from template_ref_generate import generate_template_language_help
    raw = generate_template_language_help(app.config.language)
    update_cli_doc('template_ref', raw, app)


def localized_path(app, langcode, pagename):
    href = app.builder.get_target_uri(pagename)
    href = re.sub(r'generated/[a-z]+/', 'generated/%s/' % langcode, href)
    prefix = '/'
    if langcode != 'en':
        prefix += langcode + '/'
    return prefix + href


def add_html_context(app, pagename, templatename, context, *args):
    context['localized_path'] = partial(localized_path, app)
    context['change_language_text'] = cli_index_strings()[5]


def setup(app):
    app.add_builder(EPUBHelpBuilder)
    app.add_builder(LaTeXHelpBuilder)
    app.connect('source-read', source_read_handler)
    app.connect('doctree-read', substitute)
    app.connect('builder-inited', generate_docs)
    app.connect('html-page-context', add_html_context)
    app.connect('build-finished', finished)


def finished(app, exception):
    pass
