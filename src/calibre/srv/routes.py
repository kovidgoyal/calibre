#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, sys, inspect, re, time, numbers, json as jsonlib, textwrap
from urllib import quote as urlquote
from itertools import izip
from operator import attrgetter

from calibre.srv.errors import HTTPSimpleResponse, HTTPNotFound, RouteError
from calibre.srv.utils import http_date
from calibre.utils.serialize import msgpack_dumps, json_dumps, MSGPACK_MIME

default_methods = frozenset(('HEAD', 'GET'))


def json(ctx, rd, endpoint, output):
    rd.outheaders.set('Content-Type', 'application/json; charset=UTF-8', replace_all=True)
    if isinstance(output, bytes) or hasattr(output, 'fileno'):
        ans = output  # Assume output is already UTF-8 encoded json
    else:
        ans = json_dumps(output)
    return ans


def msgpack(ctx, rd, endpoint, output):
    rd.outheaders.set('Content-Type', MSGPACK_MIME, replace_all=True)
    if isinstance(output, bytes) or hasattr(output, 'fileno'):
        ans = output  # Assume output is already msgpack encoded
    else:
        ans = msgpack_dumps(output)
    return ans


def msgpack_or_json(ctx, rd, endpoint, output):
    accept = rd.inheaders.get('Accept', all=True)
    func = msgpack if MSGPACK_MIME in accept else json
    return func(ctx, rd, endpoint, output)


json.loads, json.dumps = jsonlib.loads, jsonlib.dumps


def route_key(route):
    return route.partition('{')[0].rstrip('/')


def endpoint(route,
             methods=default_methods,
             types=None,
             auth_required=True,
             android_workaround=False,

             # Manage the HTTP caching
             # Set to None or 'no-cache' to prevent caching of this endpoint
             # Set to a number to cache for at most number hours
             # Set to a tuple (cache_type, max_age) to explicitly set the
             # Cache-Control header
             cache_control=False,

             # The HTTP code to be used when no error occurs. By default it is
             # 200 for GET and HEAD and 201 for POST
             ok_code=None,

             postprocess=None
):
    from calibre.srv.handler import Context
    from calibre.srv.http_response import RequestData

    def annotate(f):
        f.route = route.rstrip('/') or '/'
        f.route_key = route_key(f.route)
        f.types = types or {}
        f.methods = methods
        f.auth_required = auth_required
        f.android_workaround = android_workaround
        f.cache_control = cache_control
        f.postprocess = postprocess
        f.ok_code = ok_code
        f.is_endpoint = True
        argspec = inspect.getargspec(f)
        if len(argspec.args) < 2:
            raise TypeError('The endpoint %r must take at least two arguments' % f.route)
        f.__annotations__ = {
            argspec.args[0]: Context,
            argspec.args[1]: RequestData,
        }
        f.__doc__ = textwrap.dedent(f.__doc__ or '') + '\n\n' + (
            (':type %s: calibre.srv.handler.Context\n' % argspec.args[0]) +
            (':type %s: calibre.srv.http_response.RequestData\n' % argspec.args[1])
        )
        return f
    return annotate


class Route(object):

    var_pat = None

    def __init__(self, endpoint_):
        if self.var_pat is None:
            Route.var_pat = self.var_pat = re.compile(r'{(.+?)}')
        self.endpoint = endpoint_
        del endpoint_
        if not self.endpoint.route.startswith('/'):
            raise RouteError('A route must start with /, %s does not' % self.endpoint.route)
        parts = filter(None, self.endpoint.route.split('/'))
        matchers = self.matchers = []
        self.defaults = {}
        found_optional_part = False
        self.soak_up_extra = False
        self.type_checkers = self.endpoint.types.copy()

        def route_error(msg):
            return RouteError('%s is not valid: %s' % (self.endpoint.route, msg))

        for i, p in enumerate(parts):
            if p[0] == '{':
                if p[-1] != '}':
                    raise route_error('Invalid route, variable components must be in a {}')
                name = p[1:-1]
                is_sponge = name.startswith('+')
                if is_sponge:
                    if p is not parts[-1]:
                        raise route_error('Can only specify + in the last component')
                    name = name[1:]

                if '=' in name:
                    found_optional_part = i
                    name, default = name.partition('=')[::2]
                    if '{' in default or '}' in default:
                        raise route_error('The characters {} are not allowed in default values')
                    default = self.defaults[name] = eval(default)
                    if isinstance(default, (int, long, float)):
                        self.type_checkers[name] = type(default)
                    if is_sponge and not isinstance(default, type('')):
                        raise route_error('Soak up path component must have a default value of string type')
                else:
                    if found_optional_part is not False:
                        raise route_error('Cannot have non-optional path components after optional ones')
                if is_sponge:
                    self.soak_up_extra = name
                matchers.append((name, True))
            else:
                if found_optional_part is not False:
                    raise route_error('Cannot have non-optional path components after optional ones')
                matchers.append((None, p.__eq__))
        self.names = [n for n, m in matchers if n is not None]
        self.all_names = frozenset(self.names)
        self.required_names = self.all_names - frozenset(self.defaults)
        argspec = inspect.getargspec(self.endpoint)
        if len(self.names) + 2 != len(argspec.args) - len(argspec.defaults or ()):
            raise route_error('Function must take %d non-default arguments' % (len(self.names) + 2))
        if argspec.args[2:len(self.names)+2] != self.names:
            raise route_error('Function\'s argument names do not match the variable names in the route')
        if not frozenset(self.type_checkers).issubset(frozenset(self.names)):
            raise route_error('There exist type checkers that do not correspond to route variables: %r' % (set(self.type_checkers) - set(self.names)))
        self.min_size = found_optional_part if found_optional_part is not False else len(matchers)
        self.max_size = sys.maxsize if self.soak_up_extra else len(matchers)

    def matches(self, path):
        args_map = self.defaults.copy()
        num = 0
        for component, (name, matched) in izip(path, self.matchers):
            num += 1
            if matched is True:
                args_map[name] = component
            elif not matched(component):
                return False
        if self.soak_up_extra and num < len(path):
            args_map[self.soak_up_extra] += '/' + '/'.join(path[num:])
            num = len(path)
        if num < len(path):
            return False

        def check(tc, val):
            try:
                return tc(val)
            except Exception:
                raise HTTPNotFound('Argument of incorrect type')
        for name, tc in self.type_checkers.iteritems():
            args_map[name] = check(tc, args_map[name])
        return (args_map[name] for name in self.names)

    def url_for(self, **kwargs):
        names = frozenset(kwargs)
        not_spec = self.required_names - names
        if not_spec:
            raise RouteError('The required variable(s) %s were not specified for the route: %s' % (','.join(not_spec), self.endpoint.route))
        unknown = names - self.all_names
        if unknown:
            raise RouteError('The variable(s) %s are not part of the route: %s' % (','.join(unknown), self.endpoint.route))

        def quoted(x):
            if not isinstance(x, unicode) and not isinstance(x, bytes):
                x = unicode(x)
            if isinstance(x, unicode):
                x = x.encode('utf-8')
            return urlquote(x, '')
        args = {k:'' for k in self.defaults}
        args.update(kwargs)
        args = {k:quoted(v) for k, v in args.iteritems()}
        route = self.var_pat.sub(lambda m:'{%s}' % m.group(1).partition('=')[0].lstrip('+'), self.endpoint.route)
        return route.format(**args).rstrip('/')

    def __str__(self):
        return self.endpoint.route
    __unicode__ = __repr__ = __str__


class Router(object):

    def __init__(self, endpoints=None, ctx=None, url_prefix=None, auth_controller=None):
        self.routes = {}
        self.url_prefix = (url_prefix or '').rstrip('/')
        self.strip_path = None
        if self.url_prefix:
            if not self.url_prefix.startswith('/'):
                self.url_prefix = '/' + self.url_prefix
            self.strip_path = tuple(self.url_prefix[1:].split('/'))
        self.ctx = ctx
        self.auth_controller = auth_controller
        self.init_session = getattr(ctx, 'init_session', lambda ep, data:None)
        self.finalize_session = getattr(ctx, 'finalize_session', lambda ep, data, output:None)
        self.endpoints = set()
        if endpoints is not None:
            self.load_routes(endpoints)
            self.finalize()

    def add(self, endpoint):
        if endpoint in self.endpoints:
            return
        key = endpoint.route_key
        if key in self.routes:
            raise RouteError('A route with the key: %s already exists as: %s' % (key, self.routes[key]))
        self.routes[key] = Route(endpoint)
        self.endpoints.add(endpoint)

    def load_routes(self, items):
        for item in items:
            if getattr(item, 'is_endpoint', False) is True:
                self.add(item)

    def __iter__(self):
        return self.routes.itervalues()

    def finalize(self):
        try:
            lsz = max(len(r.matchers) for r in self)
        except ValueError:
            lsz = 0
        self.min_size_map = {sz:frozenset(r for r in self if r.min_size <= sz) for sz in xrange(lsz + 1)}
        self.max_size_map = {sz:frozenset(r for r in self if r.max_size >= sz) for sz in xrange(lsz + 1)}
        self.soak_routes = sorted(frozenset(r for r in self if r.soak_up_extra), key=attrgetter('min_size'), reverse=True)

    def find_route(self, path):
        if self.strip_path is not None and path[:len(self.strip_path)] == self.strip_path:
            path = path[len(self.strip_path):]
        size = len(path)
        # routes for which min_size <= size <= max_size
        routes = self.max_size_map.get(size, set()) & self.min_size_map.get(size, set())
        for route in sorted(routes, key=attrgetter('max_size'), reverse=True):
            args = route.matches(path)
            if args is not False:
                return route.endpoint, args
        for route in self.soak_routes:
            if route.min_size <= size:
                args = route.matches(path)
                if args is not False:
                    return route.endpoint, args
        raise HTTPNotFound()

    def read_cookies(self, data):
        data.cookies = c = {}

        for cval in data.inheaders.get('Cookie', all=True):
            if isinstance(cval, bytes):
                cval = cval.decode('utf-8', 'replace')
            for x in cval.split(';'):
                x = x.strip()
                if x:
                    k, v = x.partition('=')[::2]
                    if k:
                        # Since we only set simple hex encoded cookies, we dont
                        # need more sophisticated value parsing
                        c[k] = v.strip('"')

    def dispatch(self, data):
        endpoint_, args = self.find_route(data.path)
        if data.method not in endpoint_.methods:
            raise HTTPSimpleResponse(httplib.METHOD_NOT_ALLOWED)

        self.read_cookies(data)

        if endpoint_.auth_required and self.auth_controller is not None:
            self.auth_controller(data, endpoint_)

        if endpoint_.ok_code is not None:
            data.status_code = endpoint_.ok_code

        self.init_session(endpoint_, data)
        ans = endpoint_(self.ctx, data, *args)
        self.finalize_session(endpoint_, data, ans)
        outheaders = data.outheaders

        pp = endpoint_.postprocess
        if pp is not None:
            ans = pp(self.ctx, data, endpoint_, ans)

        cc = endpoint_.cache_control
        if cc is not False and 'Cache-Control' not in data.outheaders:
            if cc is None or cc == 'no-cache':
                outheaders['Expires'] = http_date(10000.0)  # A date in the past
                outheaders['Cache-Control'] = 'no-cache, must-revalidate'
                outheaders['Pragma'] = 'no-cache'
            elif isinstance(cc, numbers.Number):
                cc = int(60 * 60 * cc)
                outheaders['Cache-Control'] = 'public, max-age=%d' % cc
                if cc == 0:
                    cc -= 100000
                outheaders['Expires'] = http_date(cc + time.time())
            else:
                ctype, max_age = cc
                max_age = int(60 * 60 * max_age)
                outheaders['Cache-Control'] = '%s, max-age=%d' % (ctype, max_age)
                if max_age == 0:
                    max_age -= 100000
                outheaders['Expires'] = http_date(max_age + time.time())
        return ans

    def url_for(self, route, **kwargs):
        if route is None:
            return self.url_prefix or '/'
        route = getattr(route, 'route_key', route)
        return self.url_prefix + self.routes[route].url_for(**kwargs)
