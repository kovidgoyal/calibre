#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import sys, os, inspect, re
from sphinx.builder import StandaloneHTMLBuilder, bold
from sphinx.util import rpartition
from sphinx.ext.autodoc import get_module_charset, prepare_docstring
from docutils.statemachine import ViewList
from docutils import nodes

from genshi.template import OldTextTemplate as TextTemplate
sys.path.append(os.path.abspath('../../../'))
from calibre.linux import entry_points

class CustomBuilder(StandaloneHTMLBuilder):
    name = 'custom'


def substitute(app, doctree):
    pass

CLI_INDEX = '''\
.. include:: ../global.rst
||
.. _cli:
||
||
Command Line Interface
==========================
||
.. image:: ../images/cli.png
||
||
Documented Commands
--------------------
||
.. toctree::
    :maxdepth: 1
    ||
#for cmd, parser in documented_commands
    $cmd
#end
||
Undocumented Commands
-------------------------
||
#for cmd in undocumented_commands
  * ${cmd}
  ||
#end
||
You can see usage for undocumented commands by executing them without arguments in a terminal
'''

CLI_CMD=r'''
.. include:: ../global.rst
||
.. _$cmd:
||
#def option(opt)
:option:`${opt.get_opt_string() + ((', '+', '.join(opt._short_opts)) if opt._short_opts else '')}`
#end
$cmd
====================================================================
||
.. code-block:: none
||
    $cmdline
||
#for line in usage
#choose
#when len(line) > 0
$line
#end
#otherwise
||
#end
#end
#end
||
[options]
------------
||
#for title, desc, options in groups
#if title
$title
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
||
#end
#if desc
$desc
||
#end
#for opt in options
${option(opt)}
     ${opt.help.replace('\n', ' ').replace('*', '\\*').replace('%default', str(opt.default)) if opt.help else ''}
||
#end
#end
'''

def cli_docs(app):
    info = app.builder.info
    info(bold('creating CLI documentation...'))
    documented_cmds = []
    undocumented_cmds = []

    for script in entry_points['console_scripts']:
        module = script[script.index('=')+1:script.index(':')].strip()
        cmd = script[:script.index('=')].strip()
        module = __import__(module, fromlist=[module.split('.')[-1]])
        if hasattr(module, 'option_parser'):
            documented_cmds.append((cmd, getattr(module, 'option_parser')()))
        else:
            undocumented_cmds.append(cmd)

        documented_cmds.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        undocumented_cmds.sort()

    templ = TextTemplate(CLI_INDEX)
    raw = templ.generate(documented_commands=documented_cmds,
                         undocumented_commands=undocumented_cmds).render()
    raw = raw.replace('||', '\n')
    if not os.path.exists('cli'):
        os.makedirs('cli')
    if not os.path.exists(os.path.join('cli', 'global.rst')):
        os.link('global.rst', os.path.join('cli', 'global.rst'))
    if not os.path.exists(os.path.join('cli', 'cli-index.rst')):
        info(bold('creating cli-index...'))
        open(os.path.join('cli', 'cli-index.rst'), 'wb').write(raw)

    templ = TextTemplate(CLI_CMD)
    for cmd, parser in documented_cmds:
        usage = [i for i in parser.usage.replace('%prog', cmd).splitlines()]
        cmdline = usage[0]
        usage = usage[1:]
        usage = [i.replace(cmd, ':command:`%s`'%cmd) for i in usage]
        groups = [(None, None, parser.option_list)]
        for grp in parser.option_groups:
            groups.append((grp.title, grp.description, grp.option_list))

        raw = templ.generate(cmd=cmd, cmdline=cmdline, usage=usage, groups=groups).render()
        raw = raw.replace('||', '\n').replace('&lt;', '<').replace('&gt;', '>')
        if not os.path.exists(os.path.join('cli', cmd+'.rst')):
            info(bold('creating docs for %s...'%cmd))
            open(os.path.join('cli', cmd+'.rst'), 'wb').write(raw)


def auto_member(dirname, arguments, options, content, lineno,
                    content_offset, block_text, state, state_machine):
    name = arguments[0]
    env = state.document.settings.env

    mod_cls, obj = rpartition(name, '.')
    if not mod_cls and hasattr(env, 'autodoc_current_class'):
        mod_cls = env.autodoc_current_class
    if not mod_cls:
        mod_cls = env.currclass
    mod, cls = rpartition(mod_cls, '.')
    if not mod and hasattr(env, 'autodoc_current_module'):
        mod = env.autodoc_current_module
    if not mod:
        mod = env.currmodule

    module = __import__(mod, None, None, ['foo'])
    cls = getattr(module, cls)
    lines = inspect.getsourcelines(cls)[0]

    comment_lines = []
    for i, line in enumerate(lines):
        if re.search(r'%s\s*=\s*\S+'%obj, line) and not line.strip().startswith('#:'):
            for j in range(i-1, 0, -1):
                raw = lines[j].strip()
                if not raw.startswith('#:'):
                    break
                comment_lines.append(raw[2:])
            break
    comment_lines.reverse()
    docstring = '\n'.join(comment_lines)

    if module is not None and docstring is not None:
        docstring = docstring.decode(get_module_charset(mod))

    result = ViewList()
    result.append('.. attribute:: %s.%s'%(cls.__name__, obj), '<autodoc>')
    result.append('', '<autodoc>')

    docstring = prepare_docstring(docstring)
    for i, line in enumerate(docstring):
        result.append('    ' + line, '<docstring of %s>' % name, i)

    result.append('', '')
    result.append('    **Default**: ``%s``'%repr(getattr(cls, obj, None)), '<default memeber value>')
    result.append('', '')
    node = nodes.paragraph()
    state.nested_parse(result, content_offset, node)

    return list(node)




def setup(app):
    app.add_builder(CustomBuilder)
    app.add_directive('automember', auto_member, 1, (1, 0, 1))
    app.connect('doctree-read', substitute)
    app.connect('builder-inited', cli_docs)

