"""CPStats, a package for collecting and reporting on program statistics.

Overview
========

Statistics about program operation are an invaluable monitoring and debugging
tool. Unfortunately, the gathering and reporting of these critical values is
usually ad-hoc. This package aims to add a centralized place for gathering
statistical performance data, a structure for recording that data which
provides for extrapolation of that data into more useful information,
and a method of serving that data to both human investigators and
monitoring software. Let's examine each of those in more detail.

Data Gathering
--------------

Just as Python's `logging` module provides a common importable for gathering
and sending messages, performance statistics would benefit from a similar
common mechanism, and one that does *not* require each package which wishes
to collect stats to import a third-party module. Therefore, we choose to
re-use the `logging` module by adding a `statistics` object to it.

That `logging.statistics` object is a nested dict. It is not a custom class,
because that would 1) require libraries and applications to import a third-
party module in order to participate, 2) inhibit innovation in extrapolation
approaches and in reporting tools, and 3) be slow. There are, however, some
specifications regarding the structure of the dict.

    {
   +----"SQLAlchemy": {
   |        "Inserts": 4389745,
   |        "Inserts per Second":
   |            lambda s: s["Inserts"] / (time() - s["Start"]),
   |  C +---"Table Statistics": {
   |  o |        "widgets": {-----------+
 N |  l |            "Rows": 1.3M,      | Record
 a |  l |            "Inserts": 400,    |
 m |  e |        },---------------------+
 e |  c |        "froobles": {
 s |  t |            "Rows": 7845,
 p |  i |            "Inserts": 0,
 a |  o |        },
 c |  n +---},
 e |        "Slow Queries":
   |            [{"Query": "SELECT * FROM widgets;",
   |              "Processing Time": 47.840923343,
   |              },
   |             ],
   +----},
    }

The `logging.statistics` dict has four levels. The topmost level is nothing
more than a set of names to introduce modularity, usually along the lines of
package names. If the SQLAlchemy project wanted to participate, for example,
it might populate the item `logging.statistics['SQLAlchemy']`, whose value
would be a second-layer dict we call a "namespace". Namespaces help multiple
packages to avoid collisions over key names, and make reports easier to read,
to boot. The maintainers of SQLAlchemy should feel free to use more than one
namespace if needed (such as 'SQLAlchemy ORM'). Note that there are no case
or other syntax constraints on the namespace names; they should be chosen
to be maximally readable by humans (neither too short nor too long).

Each namespace, then, is a dict of named statistical values, such as
'Requests/sec' or 'Uptime'. You should choose names which will look
good on a report: spaces and capitalization are just fine.

In addition to scalars, values in a namespace MAY be a (third-layer)
dict, or a list, called a "collection". For example, the CherryPy StatsTool
keeps track of what each request is doing (or has most recently done)
in a 'Requests' collection, where each key is a thread ID; each
value in the subdict MUST be a fourth dict (whew!) of statistical data about
each thread. We call each subdict in the collection a "record". Similarly,
the StatsTool also keeps a list of slow queries, where each record contains
data about each slow query, in order.

Values in a namespace or record may also be functions, which brings us to:

Extrapolation
-------------

The collection of statistical data needs to be fast, as close to unnoticeable
as possible to the host program. That requires us to minimize I/O, for example,
but in Python it also means we need to minimize function calls. So when you
are designing your namespace and record values, try to insert the most basic
scalar values you already have on hand.

When it comes time to report on the gathered data, however, we usually have
much more freedom in what we can calculate. Therefore, whenever reporting
tools (like the provided StatsPage CherryPy class) fetch the contents of
`logging.statistics` for reporting, they first call `extrapolate_statistics`
(passing the whole `statistics` dict as the only argument). This makes a
deep copy of the statistics dict so that the reporting tool can both iterate
over it and even change it without harming the original. But it also expands
any functions in the dict by calling them. For example, you might have a
'Current Time' entry in the namespace with the value "lambda scope: time.time()".
The "scope" parameter is the current namespace dict (or record, if we're
currently expanding one of those instead), allowing you access to existing
static entries. If you're truly evil, you can even modify more than one entry
at a time.

However, don't try to calculate an entry and then use its value in further
extrapolations; the order in which the functions are called is not guaranteed.
This can lead to a certain amount of duplicated work (or a redesign of your
schema), but that's better than complicating the spec.

After the whole thing has been extrapolated, it's time for:

Reporting
---------

The StatsPage class grabs the `logging.statistics` dict, extrapolates it all,
and then transforms it to HTML for easy viewing. Each namespace gets its own
header and attribute table, plus an extra table for each collection. This is
NOT part of the statistics specification; other tools can format how they like.

You can control which columns are output and how they are formatted by updating
StatsPage.formatting, which is a dict that mirrors the keys and nesting of
`logging.statistics`. The difference is that, instead of data values, it has
formatting values. Use None for a given key to indicate to the StatsPage that a
given column should not be output. Use a string with formatting (such as '%.3f')
to interpolate the value(s), or use a callable (such as lambda v: v.isoformat())
for more advanced formatting. Any entry which is not mentioned in the formatting
dict is output unchanged.

Monitoring
----------

Although the HTML output takes pains to assign unique id's to each <td> with
statistical data, you're probably better off fetching /cpstats/data, which
outputs the whole (extrapolated) `logging.statistics` dict in JSON format.
That is probably easier to parse, and doesn't have any formatting controls,
so you get the "original" data in a consistently-serialized format.
Note: there's no treatment yet for datetime objects. Try time.time() instead
for now if you can. Nagios will probably thank you.

Turning Collection Off
----------------------

It is recommended each namespace have an "Enabled" item which, if False,
stops collection (but not reporting) of statistical data. Applications
SHOULD provide controls to pause and resume collection by setting these
entries to False or True, if present.


Usage
=====

To collect statistics on CherryPy applications:

    from cherrypy.lib import cpstats
    appconfig['/']['tools.cpstats.on'] = True

To collect statistics on your own code:

    import logging
    # Initialize the repository
    if not hasattr(logging, 'statistics'): logging.statistics = {}
    # Initialize my namespace
    mystats = logging.statistics.setdefault('My Stuff', {})
    # Initialize my namespace's scalars and collections
    mystats.update({
        'Enabled': True,
        'Start Time': time.time(),
        'Important Events': 0,
        'Events/Second': lambda s: (
            (s['Important Events'] / (time.time() - s['Start Time']))),
        })
    ...
    for event in events:
        ...
        # Collect stats
        if mystats.get('Enabled', False):
            mystats['Important Events'] += 1

To report statistics:

    root.cpstats = cpstats.StatsPage()

To format statistics reports:

    See 'Reporting', above.

"""

# -------------------------------- Statistics -------------------------------- #

import logging
if not hasattr(logging, 'statistics'): logging.statistics = {}

def extrapolate_statistics(scope):
    """Return an extrapolated copy of the given scope."""
    c = {}
    for k, v in list(scope.items()):
        if isinstance(v, dict):
            v = extrapolate_statistics(v)
        elif isinstance(v, (list, tuple)):
            v = [extrapolate_statistics(record) for record in v]
        elif hasattr(v, '__call__'):
            v = v(scope)
        c[k] = v
    return c


# --------------------- CherryPy Applications Statistics --------------------- #

import threading
import time

import cherrypy

appstats = logging.statistics.setdefault('CherryPy Applications', {})
appstats.update({
    'Enabled': True,
    'Bytes Read/Request': lambda s: (s['Total Requests'] and
        (s['Total Bytes Read'] / float(s['Total Requests'])) or 0.0),
    'Bytes Read/Second': lambda s: s['Total Bytes Read'] / s['Uptime'](s),
    'Bytes Written/Request': lambda s: (s['Total Requests'] and
        (s['Total Bytes Written'] / float(s['Total Requests'])) or 0.0),
    'Bytes Written/Second': lambda s: s['Total Bytes Written'] / s['Uptime'](s),
    'Current Time': lambda s: time.time(),
    'Current Requests': 0,
    'Requests/Second': lambda s: float(s['Total Requests']) / s['Uptime'](s),
    'Server Version': cherrypy.__version__,
    'Start Time': time.time(),
    'Total Bytes Read': 0,
    'Total Bytes Written': 0,
    'Total Requests': 0,
    'Total Time': 0,
    'Uptime': lambda s: time.time() - s['Start Time'],
    'Requests': {},
    })

proc_time = lambda s: time.time() - s['Start Time']


class ByteCountWrapper(object):
    """Wraps a file-like object, counting the number of bytes read."""
    
    def __init__(self, rfile):
        self.rfile = rfile
        self.bytes_read = 0
    
    def read(self, size=-1):
        data = self.rfile.read(size)
        self.bytes_read += len(data)
        return data
    
    def readline(self, size=-1):
        data = self.rfile.readline(size)
        self.bytes_read += len(data)
        return data
    
    def readlines(self, sizehint=0):
        # Shamelessly stolen from StringIO
        total = 0
        lines = []
        line = self.readline()
        while line:
            lines.append(line)
            total += len(line)
            if 0 < sizehint <= total:
                break
            line = self.readline()
        return lines
    
    def close(self):
        self.rfile.close()
    
    def __iter__(self):
        return self
    
    def next(self):
        data = self.rfile.next()
        self.bytes_read += len(data)
        return data


average_uriset_time = lambda s: s['Count'] and (s['Sum'] / s['Count']) or 0


class StatsTool(cherrypy.Tool):
    """Record various information about the current request."""
    
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_end_request', self.record_stop)
    
    def _setup(self):
        """Hook this tool into cherrypy.request.
        
        The standard CherryPy request object will automatically call this
        method when the tool is "turned on" in config.
        """
        if appstats.get('Enabled', False):
            cherrypy.Tool._setup(self)
            self.record_start()
    
    def record_start(self):
        """Record the beginning of a request."""
        request = cherrypy.serving.request
        if not hasattr(request.rfile, 'bytes_read'):
            request.rfile = ByteCountWrapper(request.rfile)
            request.body.fp = request.rfile
        
        r = request.remote
        
        appstats['Current Requests'] += 1
        appstats['Total Requests'] += 1
        appstats['Requests'][threading._get_ident()] = {
            'Bytes Read': None,
            'Bytes Written': None,
            # Use a lambda so the ip gets updated by tools.proxy later
            'Client': lambda s: '%s:%s' % (r.ip, r.port),
            'End Time': None,
            'Processing Time': proc_time,
            'Request-Line': request.request_line,
            'Response Status': None,
            'Start Time': time.time(),
            }

    def record_stop(self, uriset=None, slow_queries=1.0, slow_queries_count=100,
                    debug=False, **kwargs):
        """Record the end of a request."""
        resp = cherrypy.serving.response
        w = appstats['Requests'][threading._get_ident()]
        
        r = cherrypy.request.rfile.bytes_read
        w['Bytes Read'] = r
        appstats['Total Bytes Read'] += r
        
        if resp.stream:
            w['Bytes Written'] = 'chunked'
        else:
            cl = int(resp.headers.get('Content-Length', 0))
            w['Bytes Written'] = cl
            appstats['Total Bytes Written'] += cl
        
        w['Response Status'] = getattr(resp, 'output_status', None) or resp.status
        
        w['End Time'] = time.time()
        p = w['End Time'] - w['Start Time']
        w['Processing Time'] = p
        appstats['Total Time'] += p
        
        appstats['Current Requests'] -= 1
        
        if debug:
            cherrypy.log('Stats recorded: %s' % repr(w), 'TOOLS.CPSTATS')
        
        if uriset:
            rs = appstats.setdefault('URI Set Tracking', {})
            r = rs.setdefault(uriset, {
                'Min': None, 'Max': None, 'Count': 0, 'Sum': 0,
                'Avg': average_uriset_time})
            if r['Min'] is None or p < r['Min']:
                r['Min'] = p
            if r['Max'] is None or p > r['Max']:
                r['Max'] = p
            r['Count'] += 1
            r['Sum'] += p
        
        if slow_queries and p > slow_queries:
            sq = appstats.setdefault('Slow Queries', [])
            sq.append(w.copy())
            if len(sq) > slow_queries_count:
                sq.pop(0)


import cherrypy
cherrypy.tools.cpstats = StatsTool()


# ---------------------- CherryPy Statistics Reporting ---------------------- #

import os
thisdir = os.path.abspath(os.path.dirname(__file__))

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        json = None


missing = object()

locale_date = lambda v: time.strftime('%c', time.gmtime(v))
iso_format = lambda v: time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(v))

def pause_resume(ns):
    def _pause_resume(enabled):
        pause_disabled = ''
        resume_disabled = ''
        if enabled:
            resume_disabled = 'disabled="disabled" '
        else:
            pause_disabled = 'disabled="disabled" '
        return """
            <form action="pause" method="POST" style="display:inline">
            <input type="hidden" name="namespace" value="%s" />
            <input type="submit" value="Pause" %s/>
            </form>
            <form action="resume" method="POST" style="display:inline">
            <input type="hidden" name="namespace" value="%s" />
            <input type="submit" value="Resume" %s/>
            </form>
            """ % (ns, pause_disabled, ns, resume_disabled)
    return _pause_resume


class StatsPage(object):
    
    formatting = {
        'CherryPy Applications': {
            'Enabled': pause_resume('CherryPy Applications'),
            'Bytes Read/Request': '%.3f',
            'Bytes Read/Second': '%.3f',
            'Bytes Written/Request': '%.3f',
            'Bytes Written/Second': '%.3f',
            'Current Time': iso_format,
            'Requests/Second': '%.3f',
            'Start Time': iso_format,
            'Total Time': '%.3f',
            'Uptime': '%.3f',
            'Slow Queries': {
                'End Time': None,
                'Processing Time': '%.3f',
                'Start Time': iso_format,
                },
            'URI Set Tracking': {
                'Avg': '%.3f',
                'Max': '%.3f',
                'Min': '%.3f',
                'Sum': '%.3f',
                },
            'Requests': {
                'Bytes Read': '%s',
                'Bytes Written': '%s',
                'End Time': None,
                'Processing Time': '%.3f',
                'Start Time': None,
                },
        },
        'CherryPy WSGIServer': {
            'Enabled': pause_resume('CherryPy WSGIServer'),
            'Connections/second': '%.3f',
            'Start time': iso_format,
        },
    }
    
    
    def index(self):
        # Transform the raw data into pretty output for HTML
        yield """
<html>
<head>
    <title>Statistics</title>
<style>

th, td {
    padding: 0.25em 0.5em;
    border: 1px solid #666699;
}

table {
    border-collapse: collapse;
}

table.stats1 {
    width: 100%;
}

table.stats1 th {
    font-weight: bold;
    text-align: right;
    background-color: #CCD5DD;
}

table.stats2, h2 {
    margin-left: 50px;
}

table.stats2 th {
    font-weight: bold;
    text-align: center;
    background-color: #CCD5DD;
}

</style>
</head>
<body>
"""
        for title, scalars, collections in self.get_namespaces():
            yield """
<h1>%s</h1>

<table class='stats1'>
    <tbody>
""" % title
            for i, (key, value) in enumerate(scalars):
                colnum = i % 3
                if colnum == 0: yield """
        <tr>"""
                yield """
            <th>%(key)s</th><td id='%(title)s-%(key)s'>%(value)s</td>""" % vars()
                if colnum == 2: yield """
        </tr>"""
            
            if colnum == 0: yield """
            <th></th><td></td>
            <th></th><td></td>
        </tr>"""
            elif colnum == 1: yield """
            <th></th><td></td>
        </tr>"""
            yield """
    </tbody>
</table>"""

            for subtitle, headers, subrows in collections:
                yield """
<h2>%s</h2>
<table class='stats2'>
    <thead>
        <tr>""" % subtitle
                for key in headers:
                    yield """
            <th>%s</th>""" % key
                yield """
        </tr>
    </thead>
    <tbody>"""
                for subrow in subrows:
                    yield """
        <tr>"""
                    for value in subrow:
                        yield """
            <td>%s</td>""" % value
                    yield """
        </tr>"""
                yield """
    </tbody>
</table>"""
        yield """
</body>
</html>
"""
    index.exposed = True
    
    def get_namespaces(self):
        """Yield (title, scalars, collections) for each namespace."""
        s = extrapolate_statistics(logging.statistics)
        for title, ns in sorted(s.items()):
            scalars = []
            collections = []
            ns_fmt = self.formatting.get(title, {})
            for k, v in sorted(ns.items()):
                fmt = ns_fmt.get(k, {})
                if isinstance(v, dict):
                    headers, subrows = self.get_dict_collection(v, fmt)
                    collections.append((k, ['ID'] + headers, subrows))
                elif isinstance(v, (list, tuple)):
                    headers, subrows = self.get_list_collection(v, fmt)
                    collections.append((k, headers, subrows))
                else:
                    format = ns_fmt.get(k, missing)
                    if format is None:
                        # Don't output this column.
                        continue
                    if hasattr(format, '__call__'):
                        v = format(v)
                    elif format is not missing:
                        v = format % v
                    scalars.append((k, v))
            yield title, scalars, collections
    
    def get_dict_collection(self, v, formatting):
        """Return ([headers], [rows]) for the given collection."""
        # E.g., the 'Requests' dict.
        headers = []
        for record in v.itervalues():
            for k3 in record:
                format = formatting.get(k3, missing)
                if format is None:
                    # Don't output this column.
                    continue
                if k3 not in headers:
                    headers.append(k3)
        headers.sort()
        
        subrows = []
        for k2, record in sorted(v.items()):
            subrow = [k2]
            for k3 in headers:
                v3 = record.get(k3, '')
                format = formatting.get(k3, missing)
                if format is None:
                    # Don't output this column.
                    continue
                if hasattr(format, '__call__'):
                    v3 = format(v3)
                elif format is not missing:
                    v3 = format % v3
                subrow.append(v3)
            subrows.append(subrow)
        
        return headers, subrows
    
    def get_list_collection(self, v, formatting):
        """Return ([headers], [subrows]) for the given collection."""
        # E.g., the 'Slow Queries' list.
        headers = []
        for record in v:
            for k3 in record:
                format = formatting.get(k3, missing)
                if format is None:
                    # Don't output this column.
                    continue
                if k3 not in headers:
                    headers.append(k3)
        headers.sort()
        
        subrows = []
        for record in v:
            subrow = []
            for k3 in headers:
                v3 = record.get(k3, '')
                format = formatting.get(k3, missing)
                if format is None:
                    # Don't output this column.
                    continue
                if hasattr(format, '__call__'):
                    v3 = format(v3)
                elif format is not missing:
                    v3 = format % v3
                subrow.append(v3)
            subrows.append(subrow)
        
        return headers, subrows
    
    if json is not None:
        def data(self):
            s = extrapolate_statistics(logging.statistics)
            cherrypy.response.headers['Content-Type'] = 'application/json'
            return json.dumps(s, sort_keys=True, indent=4)
        data.exposed = True
    
    def pause(self, namespace):
        logging.statistics.get(namespace, {})['Enabled'] = False
        raise cherrypy.HTTPRedirect('./')
    pause.exposed = True
    pause.cp_config = {'tools.allow.on': True,
                       'tools.allow.methods': ['POST']}
    
    def resume(self, namespace):
        logging.statistics.get(namespace, {})['Enabled'] = True
        raise cherrypy.HTTPRedirect('./')
    resume.exposed = True
    resume.cp_config = {'tools.allow.on': True,
                        'tools.allow.methods': ['POST']}

