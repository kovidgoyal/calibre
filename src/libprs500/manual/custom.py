#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

##    Copyright © 2008 <Author> <Email>
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import shutil, sys, os
from sphinx.builder import StandaloneHTMLBuilder, bold
from genshi.template import TextTemplate
sys.path.append(os.path.abspath('../../../'))
from libprs500.linux import entry_points

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
.. role:: mycmdopt(literal)
    :class: bold
|| 
#def option(opt)
`${opt.get_opt_string() + ((', '+', '.join(opt._short_opts)) if opt._short_opts else '')}`:mycmdopt:
#end
$cmd
====================================================================
||
Usage::
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
     ${opt.help.replace('\n', ' ').replace('%default', str(opt.default)) if opt.help else ''}
||
#end
#end
'''

def cli_docs(info):
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
        open(os.path.join('cli', cmd+'.rst'), 'wb').write(raw)

def generate(app):
    app.builder.info(bold('copying images to the build tree...'))
    shutil.rmtree('.build/html/images', True)
    shutil.copytree('images', '.build/html/images')
    shutil.rmtree('.build/html/images/.svn', True)
    shutil.rmtree('.build/html/images/.bzr', True)
    cli_docs(app.builder.info)


def setup(app):
    app.add_builder(CustomBuilder)
    app.connect('doctree-read', substitute)
    app.connect('builder-inited', generate)
