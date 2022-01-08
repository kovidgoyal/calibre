#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>


# Imports {{{
import argparse
import ast
import atexit
import bz2
import errno
import glob
import gzip
import io
import json
import os
import random
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from collections import namedtuple
from contextlib import closing
from datetime import datetime
from email.utils import parsedate
from functools import partial
from multiprocessing.pool import ThreadPool
from xml.sax.saxutils import escape, quoteattr

try:
    from html import unescape as u
except ImportError:
    from HTMLParser import HTMLParser
    u = HTMLParser().unescape

try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse


try:
    from urllib.error import URLError
    from urllib.request import urlopen, Request, build_opener
except Exception:
    from urllib2 import urlopen, Request, build_opener, URLError
# }}}

USER_AGENT = 'calibre mirror'
MR_URL = 'https://www.mobileread.com/forums/'
IS_PRODUCTION = os.path.exists('/srv/plugins')
PLUGINS = 'plugins.json.bz2'
INDEX = MR_URL + 'showpost.php?p=1362767&postcount=1'
# INDEX = 'file:///t/raw.html'

IndexEntry = namedtuple('IndexEntry', 'name url donate history uninstall deprecated thread_id')
socket.setdefaulttimeout(30)


def read(url, get_info=False):  # {{{
    if url.startswith("file://"):
        return urlopen(url).read()
    opener = build_opener()
    opener.addheaders = [
        ('User-Agent', USER_AGENT),
        ('Accept-Encoding', 'gzip,deflate'),
    ]
    # Sporadic network failures in rackspace, so retry with random sleeps
    for i in range(10):
        try:
            res = opener.open(url)
            break
        except URLError as e:
            if not isinstance(e.reason, socket.timeout) or i == 9:
                raise
            time.sleep(random.randint(10, 45))
    info = res.info()
    encoding = info.get('Content-Encoding')
    raw = res.read()
    res.close()
    if encoding and encoding.lower() in {'gzip', 'x-gzip', 'deflate'}:
        if encoding.lower() == 'deflate':
            raw = zlib.decompress(raw)
        else:
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    if get_info:
        return raw, info
    return raw
# }}}


def url_to_plugin_id(url, deprecated):
    query = parse_qs(urlparse(url).query)
    ans = (query['t'] if 't' in query else query['p'])[0]
    if deprecated:
        ans += '-deprecated'
    return ans


def parse_index(raw=None):  # {{{
    raw = raw or read(INDEX).decode('utf-8', 'replace')

    dep_start = raw.index('>Deprecated/Renamed/Retired Plugins:<')
    dpat = re.compile(r'''(?is)Donate\s*:\s*<a\s+href=['"](.+?)['"]''')
    key_pat = re.compile(r'''(?is)(History|Uninstall)\s*:\s*([^<;]+)[<;]''')
    seen = {}

    for match in re.finditer(r'''(?is)<li.+?<a\s+href=['"](https://www.mobileread.com/forums/showthread.php\?[pt]=\d+).+?>(.+?)<(.+?)</li>''', raw):
        deprecated = match.start() > dep_start
        donate = uninstall = None
        history = False
        name, url, rest = u(match.group(2)), u(match.group(1)), match.group(3)
        m = dpat.search(rest)
        if m is not None:
            donate = u(m.group(1))
        for m in key_pat.finditer(rest):
            k = m.group(1).lower()
            if k == 'history' and m.group(2).strip().lower() in {'yes', 'true'}:
                history = True
            elif k == 'uninstall':
                uninstall = tuple(x.strip() for x in m.group(2).strip().split(','))

        thread_id = url_to_plugin_id(url, deprecated)
        if thread_id in seen:
            raise ValueError(f'thread_id for {seen[thread_id]} and {name} is the same: {thread_id}')
        seen[thread_id] = name
        entry = IndexEntry(name, url, donate, history, uninstall, deprecated, thread_id)
        yield entry
# }}}


def parse_plugin_zip_url(raw):
    for m in re.finditer(r'''(?is)<a\s+href=['"](attachment.php\?[^'"]+?)['"][^>]*>([^<>]+?\.zip)\s*<''', raw):
        url, name = u(m.group(1)), u(m.group(2).strip())
        if name.lower().endswith('.zip'):
            return MR_URL + url, name
    return None, None


def load_plugins_index():
    try:
        with open(PLUGINS, 'rb') as f:
            raw = f.read()
    except OSError as err:
        if err.errno == errno.ENOENT:
            return {}
        raise
    return json.loads(bz2.decompress(raw))

# Get metadata from plugin zip file {{{


def convert_node(fields, x, names={}, import_data=None):
    name = x.__class__.__name__
    conv = lambda x:convert_node(fields, x, names=names, import_data=import_data)
    if name == 'Str':
        return x.s.decode('utf-8') if isinstance(x.s, bytes) else x.s
    elif name == 'Num':
        return x.n
    elif name == 'Constant':
        return x.value
    elif name in {'Set', 'List', 'Tuple'}:
        func = {'Set':set, 'List':list, 'Tuple':tuple}[name]
        return func(list(map(conv, x.elts)))
    elif name == 'Dict':
        keys, values = list(map(conv, x.keys)), list(map(conv, x.values))
        return dict(zip(keys, values))
    elif name == 'Call':
        if len(x.args) != 1 and len(x.keywords) != 0:
            raise TypeError(f'Unsupported function call for fields: {fields}')
        return tuple(map(conv, x.args))[0]
    elif name == 'Name':
        if x.id not in names:
            if import_data is not None and x.id in import_data[0]:
                return get_import_data(x.id, import_data[0][x.id], *import_data[1:])
            raise ValueError(f'Could not find name {x.id} for fields: {fields}')
        return names[x.id]
    elif name == 'BinOp':
        if x.right.__class__.__name__ == 'Str':
            return x.right.s.decode('utf-8') if isinstance(x.right.s, bytes) else x.right.s
        if x.right.__class__.__name__ == 'Constant' and isinstance(x.right.value, str):
            return x.right.value
    elif name == 'Attribute':
        return conv(getattr(conv(x.value), x.attr))
    raise TypeError(f'Unknown datatype {x} for fields: {fields}')


Alias = namedtuple('Alias', 'name asname')


class Module:
    pass


def get_import_data(name, mod, zf, names):
    mod = mod.split('.')
    if mod[0] == 'calibre_plugins':
        mod = mod[2:]
    is_module_import = not mod
    if is_module_import:
        mod = [name]
    mod = '/'.join(mod) + '.py'
    if mod in names:
        raw = zf.open(names[mod]).read()
        module = ast.parse(raw, filename='__init__.py')
        top_level_assigments = [x for x in ast.iter_child_nodes(module) if x.__class__.__name__ == 'Assign']
        module = Module()
        for node in top_level_assigments:
            targets = {getattr(t, 'id', None) for t in node.targets}
            targets.discard(None)
            for x in targets:
                if is_module_import:
                    setattr(module, x, node.value)
                elif x == name:
                    return convert_node({x}, node.value)
        if is_module_import:
            return module
        raise ValueError(f'Failed to find name: {name!r} in module: {mod!r}')
    else:
        raise ValueError('Failed to find module: %r' % mod)


def parse_metadata(raw, namelist, zf):
    module = ast.parse(raw, filename='__init__.py')
    top_level_imports = [x for x in ast.iter_child_nodes(module) if x.__class__.__name__ == 'ImportFrom']
    top_level_classes = tuple(x for x in ast.iter_child_nodes(module) if x.__class__.__name__ == 'ClassDef')
    top_level_assigments = [x for x in ast.iter_child_nodes(module) if x.__class__.__name__ == 'Assign']
    defaults = {
        'name':'', 'description':'',
        'supported_platforms':['windows', 'osx', 'linux'],
        'version':(1, 0, 0),
        'author':'Unknown',
        'minimum_calibre_version':(0, 9, 42)
    }
    field_names = set(defaults)
    imported_names = {}

    plugin_import_found = set()
    all_imports = []
    for node in top_level_imports:
        names = getattr(node, 'names', [])
        mod = getattr(node, 'module', None)
        if names and mod:
            names = [Alias(n.name, getattr(n, 'asname', None)) for n in names]
            if mod in {
                'calibre.customize', 'calibre.customize.conversion',
                'calibre.ebooks.metadata.sources.base', 'calibre.ebooks.metadata.sources.amazon', 'calibre.ebooks.metadata.covers',
                'calibre.devices.interface', 'calibre.ebooks.metadata.fetch', 'calibre.customize.builtins',
                       } or re.match(r'calibre\.devices\.[a-z0-9]+\.driver', mod) is not None:
                inames = {n.asname or n.name for n in names}
                inames = {x for x in inames if x.lower() != x}
                plugin_import_found |= inames
            else:
                all_imports.append((mod, [n.name for n in names]))
                imported_names[names[-1].asname or names[-1].name] = mod
    if not plugin_import_found:
        return all_imports

    import_data = (imported_names, zf, namelist)

    names = {}
    for node in top_level_assigments:
        targets = {getattr(t, 'id', None) for t in node.targets}
        targets.discard(None)
        for x in targets - field_names:
            try:
                val = convert_node({x}, node.value, import_data=import_data)
            except Exception:
                pass
            else:
                names[x] = val

    def parse_class(node):
        class_assigments = [x for x in ast.iter_child_nodes(node) if x.__class__.__name__ == 'Assign']
        found = {}
        for node in class_assigments:
            targets = {getattr(t, 'id', None) for t in node.targets}
            targets.discard(None)
            fields = field_names.intersection(targets)
            if fields:
                val = convert_node(fields, node.value, names=names, import_data=import_data)
                for field in fields:
                    found[field] = val
        return found

    if top_level_classes:
        for node in top_level_classes:
            bases = {getattr(x, 'id', None) for x in node.bases}
            if not bases.intersection(plugin_import_found):
                continue
            found = parse_class(node)
            if 'name' in found and 'author' in found:
                defaults.update(found)
                return defaults
        for node in top_level_classes:
            found = parse_class(node)
            if 'name' in found and 'author' in found and 'version' in found:
                defaults.update(found)
                return defaults

    raise ValueError('Could not find plugin class')


def parse_plugin(raw, names, zf):
    ans = parse_metadata(raw, names, zf)
    if isinstance(ans, dict):
        return ans
    # The plugin is importing its base class from somewhere else, le sigh
    for mod, _ in ans:
        mod = mod.split('.')
        if mod[0] == 'calibre_plugins':
            mod = mod[2:]
        mod = '/'.join(mod) + '.py'
        if mod in names:
            raw = zf.open(names[mod]).read()
            ans = parse_metadata(raw, names, zf)
            if isinstance(ans, dict):
                return ans

    raise ValueError('Failed to find plugin class')


def get_plugin_init(zf):
    metadata = None
    names = {x.decode('utf-8') if isinstance(x, bytes) else x : x for x in zf.namelist()}
    inits = [x for x in names if x.rpartition('/')[-1] == '__init__.py']
    inits.sort(key=lambda x:x.count('/'))
    if inits and inits[0] == '__init__.py':
        metadata = names[inits[0]]
    else:
        # Legacy plugin
        for name, val in names.items():
            if name.endswith('plugin.py'):
                metadata = val
                break
    if metadata is None:
        raise ValueError('No __init__.py found in plugin')
    return zf.open(metadata).read(), names


def get_plugin_info(raw_zip):
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        raw, names = get_plugin_init(zf)
        try:
            return parse_plugin(raw, names, zf)
        except (SyntaxError, TabError, IndentationError):
            with tempfile.NamedTemporaryFile(suffix='.zip') as f:
                f.write(raw_zip)
                f.flush()
                res = subprocess.run(['python2', __file__, f.name], stdout=subprocess.PIPE)
                if res.returncode == 0:
                    return json.loads(res.stdout)
            raise


# }}}

def update_plugin_from_entry(plugin, entry):
    plugin['index_name'] = entry.name
    plugin['thread_url'] = entry.url
    for x in ('donate', 'history', 'deprecated', 'uninstall', 'thread_id'):
        plugin[x] = getattr(entry, x)


def fetch_plugin(old_index, entry):
    lm_map = {plugin['thread_id']:plugin for plugin in old_index.values()}
    raw = read(entry.url).decode('utf-8', 'replace')
    url, name = parse_plugin_zip_url(raw)
    if url is None:
        raise ValueError('Failed to find zip file URL for entry: %s' % repr(entry))
    plugin = lm_map.get(entry.thread_id, None)

    if plugin is not None:
        # Previously downloaded plugin
        lm = datetime(*tuple(map(int, re.split(r'\D', plugin['last_modified'])))[:6])
        request = Request(url)
        request.get_method = lambda : 'HEAD'
        with closing(urlopen(request)) as response:
            info = response.info()
        slm = datetime(*parsedate(info.get('Last-Modified'))[:6])
        if lm >= slm:
            # The previously downloaded plugin zip file is up-to-date
            update_plugin_from_entry(plugin, entry)
            return plugin

    raw, info = read(url, get_info=True)
    slm = datetime(*parsedate(info.get('Last-Modified'))[:6])
    plugin = get_plugin_info(raw)
    plugin['last_modified'] = slm.isoformat()
    plugin['file'] = 'staging_%s.zip' % entry.thread_id
    plugin['size'] = len(raw)
    plugin['original_url'] = url
    update_plugin_from_entry(plugin, entry)
    with open(plugin['file'], 'wb') as f:
        f.write(raw)
    return plugin


def parallel_fetch(old_index, entry):
    try:
        return fetch_plugin(old_index, entry)
    except Exception:
        import traceback
        return traceback.format_exc()


def log(*args, **kwargs):
    print(*args, **kwargs)
    with open('log', 'a') as f:
        kwargs['file'] = f
        print(*args, **kwargs)


def atomic_write(raw, name):
    with tempfile.NamedTemporaryFile(dir=os.getcwd(), delete=False) as f:
        f.write(raw)
        os.fchmod(f.fileno(), stat.S_IREAD|stat.S_IWRITE|stat.S_IRGRP|stat.S_IROTH)
        os.rename(f.name, name)


def fetch_plugins(old_index):
    ans = {}
    pool = ThreadPool(processes=10)
    entries = tuple(parse_index())
    if not entries:
        raise SystemExit('Could not find any plugins, probably the markup on the MR index page has changed')
    with closing(pool):
        result = pool.map(partial(parallel_fetch, old_index), entries)
    for entry, plugin in zip(entries, result):
        if isinstance(plugin, dict):
            ans[entry.name] = plugin
        else:
            if entry.name in old_index:
                ans[entry.name] = old_index[entry.name]
            log('Failed to get plugin', entry.name, 'at', datetime.utcnow().isoformat(), 'with error:')
            log(plugin)
    # Move staged files
    for plugin in ans.values():
        if plugin['file'].startswith('staging_'):
            src = plugin['file']
            plugin['file'] = src.partition('_')[-1]
            os.rename(src, plugin['file'])
    raw = bz2.compress(json.dumps(ans, sort_keys=True, indent=4, separators=(',', ': ')).encode('utf-8'))
    atomic_write(raw, PLUGINS)
    # Cleanup any extra .zip files
    all_plugin_files = {p['file'] for p in ans.values()}
    extra = set(glob.glob('*.zip')) - all_plugin_files
    for x in extra:
        os.unlink(x)
    return ans


def plugin_to_index(plugin, count):
    title = '<h3><img src="plugin-icon.png"><a href={} title="Plugin forum thread">{}</a></h3>'.format(  # noqa
        quoteattr(plugin['thread_url']), escape(plugin['name']))
    released = datetime(*tuple(map(int, re.split(r'\D', plugin['last_modified'])))[:6]).strftime('%e %b, %Y').lstrip()
    details = [
        'Version: <b>%s</b>' % escape('.'.join(map(str, plugin['version']))),
        'Released: <b>%s</b>' % escape(released),
        'Author: %s' % escape(plugin['author']),
        'calibre: %s' % escape('.'.join(map(str, plugin['minimum_calibre_version']))),
        'Platforms: %s' % escape(', '.join(sorted(plugin['supported_platforms']) or ['all'])),
    ]
    if plugin['uninstall']:
        details.append('Uninstall: %s' % escape(', '.join(plugin['uninstall'])))
    if plugin['donate']:
        details.append('<a href=%s title="Donate">Donate</a>' % quoteattr(plugin['donate']))
    block = []
    for li in details:
        if li.startswith('calibre:'):
            block.append('<br>')
        block.append('<li>%s</li>' % li)
    block = '<ul>%s</ul>' % ('\n'.join(block))
    downloads = ('\xa0<span class="download-count">[%d total downloads]</span>' % count) if count else ''
    zipfile = '<div class="end"><a href={} title="Download plugin" download={}>Download plugin \u2193</a>{}</div>'.format(
        quoteattr(plugin['file']), quoteattr(plugin['name'] + '.zip'), downloads)
    desc = plugin['description'] or ''
    if desc:
        desc = '<p>%s</p>' % desc
    return f'{title}\n{desc}\n{block}\n{zipfile}\n\n'


def create_index(index, raw_stats):
    plugins = []
    stats = {}
    for name in sorted(index):
        plugin = index[name]
        if not plugin['deprecated']:
            count = raw_stats.get(plugin['file'].rpartition('.')[0], 0)
            if count > 0:
                stats[plugin['name']] = count
            plugins.append(
                plugin_to_index(plugin, count))
    index = '''\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Index of calibre plugins</title>
<link rel="icon" type="image/x-icon" href="//calibre-ebook.com/favicon.ico" />
<style type="text/css">
body { background-color: #eee; }
a { text-decoration: none }
a:hover, h3:hover { color: red }
a:visited { color: blue }
ul { list-style-type: none; font-size: smaller }
li { display: inline }
li+li:before { content: " - " }
.end { border-bottom: solid 1pt black; padding-bottom: 0.5ex; margin-bottom: 4ex; }
h1 img, h3 img { vertical-align: middle; margin-right: 0.5em; }
h1 { text-align: center }
.download-count { color: gray; font-size: smaller }
</style>
</head>
<body>
<h1><img src="//manual.calibre-ebook.com/_static/logo.png">Index of calibre plugins</h1>
<div style="text-align:center"><a href="stats.html">Download counts for all plugins</a></div>
%s
</body>
</html>''' % ('\n'.join(plugins))
    raw = index.encode('utf-8')
    try:
        with open('index.html', 'rb') as f:
            oraw = f.read()
    except OSError:
        oraw = None
    if raw != oraw:
        atomic_write(raw, 'index.html')

    def plugin_stats(x):
        name, count = x
        return f'<tr><td>{escape(name)}</td><td>{count}</td></tr>\n'

    pstats = list(map(plugin_stats, sorted(stats.items(), reverse=True, key=lambda x:x[1])))
    stats = '''\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Stats for calibre plugins</title>
<link rel="icon" type="image/x-icon" href="//calibre-ebook.com/favicon.ico" />
<style type="text/css">
body { background-color: #eee; }
h1 img, h3 img { vertical-align: middle; margin-right: 0.5em; }
h1 { text-align: center }
</style>
</head>
<body>
<h1><img src="//manual.calibre-ebook.com/_static/logo.png">Stats for calibre plugins</h1>
<table>
<tr><th>Plugin</th><th>Total downloads</th></tr>
%s
</table>
</body>
</html>
    ''' % ('\n'.join(pstats))
    raw = stats.encode('utf-8')
    try:
        with open('stats.html', 'rb') as f:
            oraw = f.read()
    except OSError:
        oraw = None
    if raw != oraw:
        atomic_write(raw, 'stats.html')


_singleinstance = None


def singleinstance():
    global _singleinstance
    s = _singleinstance = socket.socket(socket.AF_UNIX)
    try:
        s.bind(b'\0calibre-plugins-mirror-singleinstance')
    except OSError as err:
        if getattr(err, 'errno', None) == errno.EADDRINUSE:
            return False
        raise
    return True


def update_stats():
    log = olog = 'stats.log'
    if not os.path.exists(log):
        return {}
    stats = {}
    if IS_PRODUCTION:
        try:
            with open('stats.json', 'rb') as f:
                stats = json.load(f)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        if os.geteuid() != 0:
            return stats
        log = 'rotated-' + log
        os.rename(olog, log)
        subprocess.check_call(['/usr/sbin/nginx', '-s', 'reopen'])
        atexit.register(os.remove, log)
    pat = re.compile(br'GET /(\d+)(?:-deprecated){0,1}\.zip')
    for line in open(log, 'rb'):
        m = pat.search(line)
        if m is not None:
            plugin = m.group(1).decode('utf-8')
            stats[plugin] = stats.get(plugin, 0) + 1
    data = json.dumps(stats, indent=2)
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    with open('stats.json', 'wb') as f:
        f.write(data)
    return stats


def parse_single_plugin(zipfile_path):
    with zipfile.ZipFile(zipfile_path) as zf:
        raw, names = get_plugin_init(zf)
        ans = parse_plugin(raw, names, zf)
        sys.stdout.write(json.dumps(ans, ensure_ascii=True))


def main():
    p = argparse.ArgumentParser(
        description='Mirror calibre plugins from the forums. Or parse a single plugin zip file'
        ' if specified on the command line'
    )
    p.add_argument('plugin_path', nargs='?', default='', help='Path to plugin zip file to parse')
    WORKDIR = '/srv/plugins' if IS_PRODUCTION else '/t/plugins'
    p.add_argument('-o', '--output-dir', default=WORKDIR, help='Where to place the mirrored plugins. Default is: ' + WORKDIR)
    args = p.parse_args()
    if args.plugin_path:
        return parse_single_plugin(args.plugin_path)

    os.makedirs(args.output_dir, exist_ok=True)
    os.chdir(args.output_dir)
    if os.geteuid() == 0 and not singleinstance():
        print('Another instance of plugins-mirror is running', file=sys.stderr)
        raise SystemExit(1)
    open('log', 'w').close()
    stats = update_stats()
    try:
        plugins_index = load_plugins_index()
        plugins_index = fetch_plugins(plugins_index)
        create_index(plugins_index, stats)
    except KeyboardInterrupt:
        raise SystemExit('Exiting on user interrupt')
    except Exception:
        import traceback
        log('Failed to run at:', datetime.utcnow().isoformat())
        log(traceback.format_exc())
        raise SystemExit(1)


def test_parse():  # {{{
    raw = read(INDEX).decode('utf-8', 'replace')

    old_entries = []
    from lxml import html
    root = html.fromstring(raw)
    list_nodes = root.xpath('//div[@id="post_message_1362767"]/ul/li')
    # Add our deprecated plugins which are nested in a grey span
    list_nodes.extend(root.xpath('//div[@id="post_message_1362767"]/span/ul/li'))
    for list_node in list_nodes:
        name = list_node.xpath('a')[0].text_content().strip()
        url = list_node.xpath('a/@href')[0].strip()

        description_text = list_node.xpath('i')[0].text_content()
        description_parts = description_text.partition('Version:')

        details_text = description_parts[1] + description_parts[2].replace('\r\n','')
        details_pairs = details_text.split(';')
        details = {}
        for details_pair in details_pairs:
            pair = details_pair.split(':')
            if len(pair) == 2:
                key = pair[0].strip().lower()
                value = pair[1].strip()
                details[key] = value

        donation_node = list_node.xpath('i/span/a/@href')
        donate = donation_node[0] if donation_node else None
        uninstall = tuple(x.strip() for x in details.get('uninstall', '').strip().split(',') if x.strip()) or None
        history = details.get('history', 'No').lower() in ['yes', 'true']
        deprecated = details.get('deprecated', 'No').lower() in ['yes', 'true']
        old_entries.append(IndexEntry(name, url, donate, history, uninstall, deprecated, url_to_plugin_id(url, deprecated)))

    new_entries = tuple(parse_index(raw))
    for i, entry in enumerate(old_entries):
        if entry != new_entries[i]:
            print(f'The new entry: {new_entries[i]} != {entry}')
            raise SystemExit(1)
    pool = ThreadPool(processes=20)
    urls = [e.url for e in new_entries]
    data = pool.map(read, urls)
    for url, raw in zip(urls, data):
        sys.stdout.flush()
        root = html.fromstring(raw)
        attachment_nodes = root.xpath('//fieldset/table/tr/td/a')
        full_url = None
        for attachment_node in attachment_nodes:
            filename = attachment_node.text_content().lower()
            if filename.find('.zip') != -1:
                full_url = MR_URL + attachment_node.attrib['href']
                break
        new_url, aname = parse_plugin_zip_url(raw)
        if new_url != full_url:
            print(f'new url ({aname}): {new_url} != {full_url} for plugin at: {url}')
            raise SystemExit(1)

# }}}


def test_parse_metadata():  # {{{
    raw = b'''\
import os
from calibre.customize import FileTypePlugin

MV = (0, 7, 53)

class HelloWorld(FileTypePlugin):

    name                = _('name') # Name of the plugin
    description         = {1, 2}
    supported_platforms = ['windows', 'osx', 'linux'] # Platforms this plugin will run on
    author              = u'Acme Inc.' # The author of this plugin
    version             = {1:'a', 'b':2}
    file_types          = set(['epub', 'mobi']) # The file types that this plugin will be applied to
    on_postprocess      = True # Run this plugin after conversion is complete
    minimum_calibre_version = MV
    '''
    vals = {
        'name':'name', 'description':{1, 2},
        'supported_platforms':['windows', 'osx', 'linux'],
        'author':'Acme Inc.', 'version':{1:'a', 'b':2},
        'minimum_calibre_version':(0, 7, 53)}
    assert parse_metadata(raw, None, None) == vals
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('very/lovely.py', raw.replace(b'MV = (0, 7, 53)', b'from very.ver import MV'))
        zf.writestr('very/ver.py', b'MV = (0, 7, 53)')
        zf.writestr('__init__.py', b'from xxx import yyy\nfrom very.lovely import HelloWorld')
    assert get_plugin_info(buf.getvalue()) == vals

# }}}


if __name__ == '__main__':
    # test_parse_metadata()
    # import pprint
    # pprint.pprint(get_plugin_info(open(sys.argv[-1], 'rb').read()))

    main()
