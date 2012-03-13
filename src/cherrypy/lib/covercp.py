"""Code-coverage tools for CherryPy.

To use this module, or the coverage tools in the test suite,
you need to download 'coverage.py', either Gareth Rees' `original 
implementation <http://www.garethrees.org/2001/12/04/python-coverage/>`_
or Ned Batchelder's `enhanced version:
<http://www.nedbatchelder.com/code/modules/coverage.html>`_

To turn on coverage tracing, use the following code::

    cherrypy.engine.subscribe('start', covercp.start)

DO NOT subscribe anything on the 'start_thread' channel, as previously
recommended. Calling start once in the main thread should be sufficient
to start coverage on all threads. Calling start again in each thread
effectively clears any coverage data gathered up to that point.

Run your code, then use the ``covercp.serve()`` function to browse the
results in a web browser. If you run this module from the command line,
it will call ``serve()`` for you.
"""

import re
import sys
import cgi
from cherrypy._cpcompat import quote_plus
import os, os.path
localFile = os.path.join(os.path.dirname(__file__), "coverage.cache")

the_coverage = None
try:
    from coverage import coverage
    the_coverage = coverage(data_file=localFile)
    def start():
        the_coverage.start()
except ImportError:
    # Setting the_coverage to None will raise errors
    # that need to be trapped downstream.
    the_coverage = None
    
    import warnings
    warnings.warn("No code coverage will be performed; coverage.py could not be imported.")
    
    def start():
        pass
start.priority = 20

TEMPLATE_MENU = """<html>
<head>
    <title>CherryPy Coverage Menu</title>
    <style>
        body {font: 9pt Arial, serif;}
        #tree {
            font-size: 8pt;
            font-family: Andale Mono, monospace;
            white-space: pre;
            }
        #tree a:active, a:focus {
            background-color: black;
            padding: 1px;
            color: white;
            border: 0px solid #9999FF;
            -moz-outline-style: none;
            }
        .fail { color: red;}
        .pass { color: #888;}
        #pct { text-align: right;}
        h3 {
            font-size: small;
            font-weight: bold;
            font-style: italic;
            margin-top: 5px; 
            }
        input { border: 1px solid #ccc; padding: 2px; }
        .directory {
            color: #933;
            font-style: italic;
            font-weight: bold;
            font-size: 10pt;
            }
        .file {
            color: #400;
            }
        a { text-decoration: none; }
        #crumbs {
            color: white;
            font-size: 8pt;
            font-family: Andale Mono, monospace;
            width: 100%;
            background-color: black;
            }
        #crumbs a {
            color: #f88;
            }
        #options {
            line-height: 2.3em;
            border: 1px solid black;
            background-color: #eee;
            padding: 4px;
            }
        #exclude {
            width: 100%;
            margin-bottom: 3px;
            border: 1px solid #999;
            }
        #submit {
            background-color: black;
            color: white;
            border: 0;
            margin-bottom: -9px;
            }
    </style>
</head>
<body>
<h2>CherryPy Coverage</h2>"""

TEMPLATE_FORM = """
<div id="options">
<form action='menu' method=GET>
    <input type='hidden' name='base' value='%(base)s' />
    Show percentages <input type='checkbox' %(showpct)s name='showpct' value='checked' /><br />
    Hide files over <input type='text' id='pct' name='pct' value='%(pct)s' size='3' />%%<br />
    Exclude files matching<br />
    <input type='text' id='exclude' name='exclude' value='%(exclude)s' size='20' />
    <br />

    <input type='submit' value='Change view' id="submit"/>
</form>
</div>""" 

TEMPLATE_FRAMESET = """<html>
<head><title>CherryPy coverage data</title></head>
<frameset cols='250, 1*'>
    <frame src='menu?base=%s' />
    <frame name='main' src='' />
</frameset>
</html>
"""

TEMPLATE_COVERAGE = """<html>
<head>
    <title>Coverage for %(name)s</title>
    <style>
        h2 { margin-bottom: .25em; }
        p { margin: .25em; }
        .covered { color: #000; background-color: #fff; }
        .notcovered { color: #fee; background-color: #500; }
        .excluded { color: #00f; background-color: #fff; }
         table .covered, table .notcovered, table .excluded
             { font-family: Andale Mono, monospace;
               font-size: 10pt; white-space: pre; }

         .lineno { background-color: #eee;}
         .notcovered .lineno { background-color: #000;}
         table { border-collapse: collapse;
    </style>
</head>
<body>
<h2>%(name)s</h2>
<p>%(fullpath)s</p>
<p>Coverage: %(pc)s%%</p>"""

TEMPLATE_LOC_COVERED = """<tr class="covered">
    <td class="lineno">%s&nbsp;</td>
    <td>%s</td>
</tr>\n"""
TEMPLATE_LOC_NOT_COVERED = """<tr class="notcovered">
    <td class="lineno">%s&nbsp;</td>
    <td>%s</td>
</tr>\n"""
TEMPLATE_LOC_EXCLUDED = """<tr class="excluded">
    <td class="lineno">%s&nbsp;</td>
    <td>%s</td>
</tr>\n"""

TEMPLATE_ITEM = "%s%s<a class='file' href='report?name=%s' target='main'>%s</a>\n"

def _percent(statements, missing):
    s = len(statements)
    e = s - len(missing)
    if s > 0:
        return int(round(100.0 * e / s))
    return 0

def _show_branch(root, base, path, pct=0, showpct=False, exclude="",
                 coverage=the_coverage):
    
    # Show the directory name and any of our children
    dirs = [k for k, v in root.items() if v]
    dirs.sort()
    for name in dirs:
        newpath = os.path.join(path, name)
        
        if newpath.lower().startswith(base):
            relpath = newpath[len(base):]
            yield "| " * relpath.count(os.sep)
            yield "<a class='directory' href='menu?base=%s&exclude=%s'>%s</a>\n" % \
                   (newpath, quote_plus(exclude), name)
        
        for chunk in _show_branch(root[name], base, newpath, pct, showpct, exclude, coverage=coverage):
            yield chunk
    
    # Now list the files
    if path.lower().startswith(base):
        relpath = path[len(base):]
        files = [k for k, v in root.items() if not v]
        files.sort()
        for name in files:
            newpath = os.path.join(path, name)
            
            pc_str = ""
            if showpct:
                try:
                    _, statements, _, missing, _ = coverage.analysis2(newpath)
                except:
                    # Yes, we really want to pass on all errors.
                    pass
                else:
                    pc = _percent(statements, missing)
                    pc_str = ("%3d%% " % pc).replace(' ','&nbsp;')
                    if pc < float(pct) or pc == -1:
                        pc_str = "<span class='fail'>%s</span>" % pc_str
                    else:
                        pc_str = "<span class='pass'>%s</span>" % pc_str
            
            yield TEMPLATE_ITEM % ("| " * (relpath.count(os.sep) + 1),
                                   pc_str, newpath, name)

def _skip_file(path, exclude):
    if exclude:
        return bool(re.search(exclude, path))

def _graft(path, tree):
    d = tree
    
    p = path
    atoms = []
    while True:
        p, tail = os.path.split(p)
        if not tail:
            break
        atoms.append(tail)
    atoms.append(p)
    if p != "/":
        atoms.append("/")
    
    atoms.reverse()
    for node in atoms:
        if node:
            d = d.setdefault(node, {})

def get_tree(base, exclude, coverage=the_coverage):
    """Return covered module names as a nested dict."""
    tree = {}
    runs = coverage.data.executed_files()
    for path in runs:
        if not _skip_file(path, exclude) and not os.path.isdir(path):
            _graft(path, tree)
    return tree

class CoverStats(object):
    
    def __init__(self, coverage, root=None):
        self.coverage = coverage
        if root is None:
            # Guess initial depth. Files outside this path will not be
            # reachable from the web interface.
            import cherrypy
            root = os.path.dirname(cherrypy.__file__)
        self.root = root
    
    def index(self):
        return TEMPLATE_FRAMESET % self.root.lower()
    index.exposed = True
    
    def menu(self, base="/", pct="50", showpct="",
             exclude=r'python\d\.\d|test|tut\d|tutorial'):
        
        # The coverage module uses all-lower-case names.
        base = base.lower().rstrip(os.sep)
        
        yield TEMPLATE_MENU
        yield TEMPLATE_FORM % locals()
        
        # Start by showing links for parent paths
        yield "<div id='crumbs'>"
        path = ""
        atoms = base.split(os.sep)
        atoms.pop()
        for atom in atoms:
            path += atom + os.sep
            yield ("<a href='menu?base=%s&exclude=%s'>%s</a> %s"
                   % (path, quote_plus(exclude), atom, os.sep))
        yield "</div>"
        
        yield "<div id='tree'>"
        
        # Then display the tree
        tree = get_tree(base, exclude, self.coverage)
        if not tree:
            yield "<p>No modules covered.</p>"
        else:
            for chunk in _show_branch(tree, base, "/", pct,
                                      showpct=='checked', exclude, coverage=self.coverage):
                yield chunk
        
        yield "</div>"
        yield "</body></html>"
    menu.exposed = True
    
    def annotated_file(self, filename, statements, excluded, missing):
        source = open(filename, 'r')
        buffer = []
        for lineno, line in enumerate(source.readlines()):
            lineno += 1
            line = line.strip("\n\r")
            empty_the_buffer = True
            if lineno in excluded:
                template = TEMPLATE_LOC_EXCLUDED
            elif lineno in missing:
                template = TEMPLATE_LOC_NOT_COVERED
            elif lineno in statements:
                template = TEMPLATE_LOC_COVERED
            else:
                empty_the_buffer = False
                buffer.append((lineno, line))
            if empty_the_buffer:
                for lno, pastline in buffer:
                    yield template % (lno, cgi.escape(pastline))
                buffer = []
                yield template % (lineno, cgi.escape(line))
    
    def report(self, name):
        filename, statements, excluded, missing, _ = self.coverage.analysis2(name)
        pc = _percent(statements, missing)
        yield TEMPLATE_COVERAGE % dict(name=os.path.basename(name),
                                       fullpath=name,
                                       pc=pc)
        yield '<table>\n'
        for line in self.annotated_file(filename, statements, excluded,
                                        missing):
            yield line
        yield '</table>'
        yield '</body>'
        yield '</html>'
    report.exposed = True


def serve(path=localFile, port=8080, root=None):
    if coverage is None:
        raise ImportError("The coverage module could not be imported.")
    from coverage import coverage
    cov = coverage(data_file = path)
    cov.load()
    
    import cherrypy
    cherrypy.config.update({'server.socket_port': int(port),
                            'server.thread_pool': 10,
                            'environment': "production",
                            })
    cherrypy.quickstart(CoverStats(cov, root))

if __name__ == "__main__":
    serve(*tuple(sys.argv[1:]))

