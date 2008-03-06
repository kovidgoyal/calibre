#!/usr/bin/env  python
##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
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
''''''

import sys, glob, mechanize, time, subprocess, os, shutil, re
from tempfile import NamedTemporaryFile
from genshi.template import TemplateLoader, MarkupTemplate


# Load libprs500 from source copy
sys.path.insert(1, os.path.dirname(os.path.dirname(os.getcwdu())))

from libprs500.ebooks.BeautifulSoup import BeautifulSoup
from libprs500.linux import entry_points
from libprs500 import __appname__, __author__, __version__

class Template(MarkupTemplate):
    
    def generate(self, *args, **kwargs):
        kwdargs = dict(app=__appname__, author=__author__.partition('<')[0].strip(),
                          version=__version__, footer=True)
        kwdargs.update(kwargs)
        return MarkupTemplate.generate(self, *args, **kwdargs)

loader = TemplateLoader(os.path.abspath('templates'), auto_reload=True, 
                        variable_lookup='strict', default_class=Template)

def browser():
    opener = mechanize.Browser()
    opener.set_handle_refresh(True)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    return opener

def validate(file=None):
    br = browser()
    files = [file] if file is not None else glob.glob('build/*.html')
    for f in files:
        print 'Validating', f
        raw = open(f).read()
        br.open('http://validator.w3.org/#validate_by_input')
        br.form = tuple(br.forms())[2]
        br.form.set_value(raw, id='fragment')
        res = br.submit()
        soup = BeautifulSoup(res.read())
        if soup.find('div', id='result').find(id='congrats') is None:
            print 'Invalid HTML in', f
            t = NamedTemporaryFile()
            t.write(unicode(soup).encode('utf-8'))
            subprocess.call(('xdg-open', t.name))
            time.sleep(2)
            return
                        
def clean():
    if os.path.exists('build'):
        shutil.rmtree('build')
    return 0
                
def compile_help():
    QTDIR = '/usr/local/Trolltech/Qt-4.4.0-beta1'
    QTBIN = QTDIR + '/bin'
    QTLIB = QTDIR + '/lib'
    QCG = os.path.join(QTBIN, 'qcollectiongenerator')
    QTA = os.path.join(QTBIN, 'assistant')
    os.environ['LD_LIBRARY_PATH'] = QTLIB
    for f in ('build/%s.qch'%__appname__, 'build/%s.qhc'%__appname__):
        if os.path.exists(f):
            os.unlink(f)
    cwd = os.getcwd()
    os.chdir('build')
    try:
        subprocess.check_call((QCG, __appname__+'.qhcp', '-o', __appname__+'.qhc'))
        subprocess.call((QTA, '-collectionFile', __appname__+'.qhc'))
    finally:
        os.chdir(cwd)
     

def get_subsections(section, level=0, max_level=1, prefix='templates'):
    src = os.path.join(prefix, section)
    if not os.path.exists(src):
        return []
    soup = BeautifulSoup(open(src, 'rb').read().decode('UTF-8'))
    toc = soup.find(id='toc')
    if toc is None:
        return []
    return [dict(href=section+a['href'] if a['href'].startswith('#') else a['href'], 
                 title=a.string.replace('&amp;', '&'), 
                 subsections=get_subsections(a['href'], level=1, 
                        prefix=prefix, max_level=max_level) if level<max_level else [])\
             for a in toc.findAll('a', href=True)]

def qhp():
    render()
    cli_docs()
    
    toc = get_subsections('start.html', prefix='build')
    toc.insert(0, dict(title='Start', href='start.html', subsections=[]))
    files = []
    for loc in ('*.html', 'images'+os.sep+'*', 'styles'+os.sep+'*'):
        files += glob.glob(os.path.join('build', loc))
    files = [i.partition(os.sep)[2] for i in files]
    
    tpl = loader.load('app.qhp')
    raw = tpl.generate(toc=toc, files=files).render('xml')
    open(os.path.join('build', __appname__+'.qhp'), 'wb').write(raw)
    
    tpl = loader.load('app.qhcp')
    open(os.path.join('build', __appname__+'.qhcp'), 'wb').write(tpl.generate().render('xml'))
    about = open('templates'+os.sep+'about.txt', 'rb').read()
    about = re.sub(r'\$\{app\}', __appname__, about)
    about = re.sub(r'\$\{author\}', __author__.partition('<')[0].strip(), about)
    open('build'+os.sep+'about.txt', 'wb').write(about)
    compile_help()

def cli_docs():
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
    
    for cmd, parser in documented_cmds:
        template = loader.load('cli-cmd.html')
        open('build/cli-%s.html'%cmd, 'wb').write(
            template.generate(cmd=cmd, parser=parser).render(doctype='xhtml'))
    
    documented = [i[0] for i in documented_cmds]
    template = loader.load('cli-index.html')
    
    open('build/cli-index.html', 'wb').write(
        template.generate(documented=documented, undocumented=undocumented_cmds).render(doctype='xhtml'))
        

def html():
    toc = get_subsections('start.html', prefix='build')
    toc.insert(0, dict(title='Start', href='start.html', subsections=[]))
    template = loader.load('navtree.html')
    dt = ('html', "-//W3C//DTD HTML 4.01 Transitional//EN",
                    "http://www.w3.org/TR/html4/loose.dtd")
    raw = template.generate(footer=False, toc=toc).render(doctype=dt)
    raw = re.sub(r'<html[^<>]+>', '<html lang="en">', raw)
    raw = re.sub(r'<(script|link|style)([^<>])+/>', '<\1 \2></\1>', raw)
    open('build'+os.sep+'navtree.html', 'wb').write(raw)
            

def render():
    for d in ('images', 'styles'):
        tgt = os.path.join('build', d)
        if not os.path.exists(tgt):
            os.mkdir(tgt)
        for f in glob.glob(d+os.sep+'*'):
            if os.path.isfile(f):
                ftgt = os.path.join(tgt, os.path.basename(f))
                if os.path.exists(ftgt):
                    os.unlink(ftgt)
                os.link(f, ftgt)
    
    sections = [i['href'] for i in get_subsections('start.html')]
    sections.remove('cli-index.html')
    
    for f in sections + ['index.html', 'start.html']:
        kwdargs = {}
        if not isinstance(f, basestring):
            f, kwdargs = f
        dt = f.rpartition('.')[-1]
        if dt == 'html':
            dt = 'xhtml'
        if f == 'index.html':
            dt=('html', '-//W3C//DTD XHTML 1.0 Frameset//EN', 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd')
        
        raw = loader.load(f).generate(**kwdargs).render(doctype=dt)
        open(os.path.join('build', f), 'wb').write(raw)
    

def all(opts):
    clean()
    os.mkdir('build')
    qhp()
    html()
    if opts.validate:
        validate()
    
    return 0

if __name__ == '__main__':
    if not os.path.exists('build'):
        os.mkdir('build')

    from libprs500 import OptionParser
    parser = OptionParser(usage='%prog [options] target [arguments to target]')
    parser.add_option('--validate', default=False, action='store_true',
                      help='Validate all HTML files against their DTDs.')
    opts, args = parser.parse_args()
    
    if len(args) == 0:
        clean()
        sys.exit(all(opts))
    elif len(args) == 1:
        func = eval(args[0])
        fargs = []
        if args[0] == 'all':
            fargs = [opts]
    elif len(args) > 1:
        func = eval(args[0])
        fargs = args[1:]
        if func is None:
            print >>sys.stderr, 'Unknown target', sys.argv(1)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    sys.exit(func(*fargs))
    