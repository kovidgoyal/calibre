#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import annotationlib
import http.client
import inspect
import json as jsonlib
import numbers
import re
import sys
import textwrap
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Concatenate, Literal, Protocol, Self, cast
from urllib.parse import quote as urlquote

from calibre.srv.errors import HTTPNotFound, HTTPSimpleResponse, RouteError
from calibre.srv.utils import http_date
from calibre.utils.serialize import MSGPACK_MIME, json_dumps, msgpack_dumps

if TYPE_CHECKING:
    from calibre.srv.auth import AuthController
    from calibre.srv.handler import Context
    from calibre.srv.http_response import RequestData
else:
    Context = RequestData = None

default_methods = frozenset(('HEAD', 'GET'))


class JSONEndpoint:
    def loads(self, *a: object, **kw: object) -> object:
        return jsonlib.loads(*a, **kw)  # ty: ignore[invalid-argument-type]

    def dumps(self, *a: object, **kw: object) -> str:
        return jsonlib.dumps(*a, **kw)  # ty: ignore[invalid-argument-type]

    def __call__(self, ctx: Context, rd: RequestData, endpoint: RouteFunction, output: object) -> object:
        rd.outheaders.set('Content-Type', 'application/json; charset=UTF-8', replace_all=True)
        if isinstance(output, bytes) or hasattr(output, 'fileno'):
            ans = output  # Assume output is already UTF-8 encoded json
        else:
            ans = json_dumps(output)
        return ans


json = JSONEndpoint()


def msgpack(ctx: Context, rd: RequestData, endpoint: RouteFunction, output: object) -> object:
    rd.outheaders.set('Content-Type', MSGPACK_MIME, replace_all=True)
    if isinstance(output, bytes) or hasattr(output, 'fileno'):
        ans = output  # Assume output is already msgpack encoded
    else:
        ans = msgpack_dumps(output)
    return ans


def msgpack_or_json(ctx: Context, rd: RequestData, endpoint: RouteFunction, output: object) -> object:
    accept = rd.inheaders.get('Accept', all=True)
    func = msgpack if MSGPACK_MIME in accept else json
    return func(ctx, rd, endpoint, output)


def route_key(route: str) -> str:
    return route.partition('{')[0].rstrip('/')  # ]]]}}))


class EndpointFunction(Protocol):
    def __call__(self, ctx: Context, rd: RequestData, *path_segments: object) -> object: ...


# Converts the output of an endpoint, the result is passed to
# HTTPConnection.finalize_output(), which accepts many kinds of output
PostProcessFunc = Callable[[Context, RequestData, 'RouteFunction', object], object]


class types_dict(dict[str, type]):
    _hash_val: int

    def __new__(cls, types: dict[str, type]) -> Self:
        ans = super().__new__(cls, types)
        ans._hash_val = hash(tuple(sorted(types.items())))
        return ans

    def __hash__(self) -> int:
        return self._hash_val


@dataclass(unsafe_hash=True)
class RouteFunction:
    f: Callable[..., object]
    route: str
    route_key: str
    types: types_dict
    methods: frozenset[str]
    auth_required: bool
    android_workaround: bool
    cache_control: int | float | bool | Literal['no-cache'] | tuple[str, int] | None
    ok_code: int | None
    postprocess: PostProcessFunc | None
    needs_db_write: bool

    is_endpoint: bool = True

    @property
    def __name__(self) -> str:
        return self.f.__name__  # ty: ignore[unresolved-attribute]

    def __call__(self, ctx: Context, rd: RequestData, *path_segments: object) -> object:
        return self.f(ctx, rd, *path_segments)


def positional_args(f: Callable[..., object]) -> tuple[list[str], int]:
    """Return the names of the positional arguments of f and how many of them
    have default values. Equivalent to the args and defaults of
    inspect.getfullargspec(), except that annotations are not evaluated, as
    they can refer to names imported only when type checking."""
    if inspect.ismethod(f):
        f = f.__func__
    sig = inspect.signature(f, follow_wrapped=False, annotation_format=annotationlib.Format.FORWARDREF)
    params = [p for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return [p.name for p in params], sum(1 for p in params if p.default is not p.empty)


def endpoint[**P, R](
    route: str,
    methods: frozenset[str] | set[str] | tuple[str, ...] = default_methods,
    types: dict[str, type] | None = None,
    auth_required: bool = True,
    android_workaround: bool = False,
    # Manage the HTTP caching
    # Set to None or 'no-cache' to prevent caching of this endpoint
    # Set to a number to cache for at most number hours
    # Set to a tuple (cache_type, max_age) to explicitly set the
    # Cache-Control header
    cache_control: int | float | bool | Literal['no-cache'] | tuple[str, int] | None = False,
    # The HTTP code to be used when no error occurs. By default it is
    # 200 for GET and HEAD and 201 for POST
    ok_code: int | None = None,
    # Converts the output of the endpoint function
    postprocess: Callable[[Context, RequestData, RouteFunction, R], object] | None = None,
    # Needs write access to the calibre database
    needs_db_write: bool = False,
) -> Callable[[Callable[Concatenate[Context, RequestData, P], R]], RouteFunction]:
    from calibre.srv.handler import Context  # ruff: ignore[unused-import]
    from calibre.srv.http_response import RequestData  # ruff: ignore[unused-import]

    def annotate[**P](f: Callable[Concatenate[Context, RequestData, P], R]) -> RouteFunction:
        r = route.rstrip('/') or '/'
        ans = RouteFunction(
            f,
            route=r,
            route_key=route_key(r),
            types=types_dict(types or {}),
            methods=frozenset(methods),
            auth_required=auth_required,
            android_workaround=android_workaround,
            cache_control=cache_control,
            postprocess=cast('PostProcessFunc | None', postprocess),
            ok_code=ok_code,
            needs_db_write=needs_db_write,
        )
        args = positional_args(f)[0]
        if len(args) < 2:
            raise TypeError(f'The endpoint {r!r} must take at least two arguments')
        ans.__doc__ = (
            textwrap.dedent(f.__doc__ or '')
            + '\n\n'
            + ((f':type {args[0]}: calibre.srv.handler.Context\n') + (f':type {args[1]}: calibre.srv.http_response.RequestData\n'))
        )
        return ans

    return annotate


class Route:
    var_pat: re.Pattern[str] | None = None

    def __init__(self, endpoint_: RouteFunction) -> None:
        if self.var_pat is None:
            Route.var_pat = self.var_pat = re.compile(r'{(.+?)}')
        self.endpoint = endpoint_
        del endpoint_
        if not self.endpoint.route.startswith('/'):
            raise RouteError(f'A route must start with /, {self.endpoint.route} does not')
        parts = list(filter(None, self.endpoint.route.split('/')))
        matchers: list[tuple[str | None, Literal[True] | Callable[[str], bool]]] = []
        self.matchers = matchers
        self.defaults: dict[str, object] = {}
        found_optional_part: int | Literal[False] = False
        self.soak_up_extra: str | Literal[False] = False
        self.type_checkers: dict[str, type] = self.endpoint.types.copy()

        def route_error(msg: str) -> RouteError:
            return RouteError(f'{self.endpoint.route} is not valid: {msg}')

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
                    if isinstance(default, numbers.Number):
                        self.type_checkers[name] = type(default)
                    if is_sponge and not isinstance(default, str):
                        raise route_error('Soak up path component must have a default value of string type')
                elif found_optional_part is not False:
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
        args, num_defaults = positional_args(self.endpoint.f)
        if len(self.names) + 2 != len(args) - num_defaults:
            raise route_error(f'Function {self.endpoint.f} must take {len(self.names) + 2} non-default arguments')
        if args[2 : len(self.names) + 2] != self.names:
            raise route_error("Function's argument names do not match the variable names in the route")
        if not frozenset(self.type_checkers).issubset(frozenset(self.names)):
            raise route_error(f'There exist type checkers that do not correspond to route variables: {set(self.type_checkers) - set(self.names)!r}')
        self.min_size = found_optional_part if found_optional_part is not False else len(matchers)
        self.max_size = sys.maxsize if self.soak_up_extra else len(matchers)

    def matches(self, path: tuple[str, ...]) -> Iterator[object] | Literal[False]:
        args_map = self.defaults.copy()
        num = 0
        for component, (name, matched) in zip(path, self.matchers):
            num += 1
            if matched is True:
                args_map[name] = component  # ty: ignore[invalid-assignment]
            elif not matched(component):
                return False
        if self.soak_up_extra and num < len(path):
            args_map[self.soak_up_extra] += '/' + '/'.join(path[num:])  # ty: ignore[unsupported-operator]
            num = len(path)
        if num < len(path):
            return False

        def check(tc: type, val: object) -> object:
            try:
                return tc(val)
            except Exception:
                raise HTTPNotFound('Argument of incorrect type')

        for name, tc in self.type_checkers.items():
            args_map[name] = check(tc, args_map[name])
        return (args_map[name] for name in self.names)

    def url_for(self, **kwargs: object) -> str:
        names = frozenset(kwargs)
        not_spec = self.required_names - names
        if not_spec:
            raise RouteError('The required variable(s) {} were not specified for the route: {}'.format(','.join(not_spec), self.endpoint.route))
        unknown = names - self.all_names
        if unknown:
            raise RouteError('The variable(s) {} are not part of the route: {}'.format(','.join(unknown), self.endpoint.route))

        def quoted(x: object) -> str:
            if not isinstance(x, (str, bytes)):
                x = str(x)
            if isinstance(x, str):
                x = x.encode('utf-8')
            return urlquote(x, '')

        args: dict[str, object] = {k: '' for k in self.defaults}
        args.update(kwargs)
        args = {k: quoted(v) for k, v in args.items()}
        assert self.var_pat is not None
        route = self.var_pat.sub(lambda m: '{{{}}}'.format(m.group(1).partition('=')[0].lstrip('+')), self.endpoint.route)
        return route.format(**args).rstrip('/')

    def __str__(self) -> str:
        return self.endpoint.route

    __unicode__ = __repr__ = __str__


class Router:
    def __init__(
        self,
        endpoints: Iterable[object] | None = None,
        ctx: Context | None = None,
        url_prefix: str | None = None,
        auth_controller: AuthController | None = None,
    ) -> None:
        self.routes: dict[str, Route] = {}
        self.url_prefix = (url_prefix or '').rstrip('/')
        self.strip_path: tuple[str, ...] | None = None
        if self.url_prefix:
            if not self.url_prefix.startswith('/'):
                self.url_prefix = '/' + self.url_prefix
            self.strip_path = tuple(self.url_prefix[1:].split('/'))
        self.ctx = ctx
        self.auth_controller = auth_controller
        self.init_session: Callable[[RouteFunction, RequestData], object] = getattr(ctx, 'init_session', lambda ep, data: None)
        self.finalize_session: Callable[[RouteFunction, RequestData, object], object] = getattr(ctx, 'finalize_session', lambda ep, data, output: None)
        self.endpoints: set[RouteFunction] = set()
        if endpoints is not None:
            self.load_routes(endpoints)
            self.finalize()

    def add(self, endpoint: RouteFunction) -> None:
        if endpoint in self.endpoints:
            return
        key = endpoint.route_key
        if key in self.routes:
            raise RouteError(f'A route with the key: {key} already exists as: {self.routes[key]}')
        self.routes[key] = Route(endpoint)
        self.endpoints.add(endpoint)

    def load_routes(self, items: Iterable[object]) -> None:
        for item in items:
            if getattr(item, 'is_endpoint', False) is True:
                self.add(cast('RouteFunction', item))

    def __iter__(self) -> Iterator[Route]:
        yield from self.routes.values()

    def finalize(self) -> None:
        try:
            lsz = max(len(r.matchers) for r in self)
        except ValueError:
            lsz = 0
        self.min_size_map = {sz: frozenset(r for r in self if r.min_size <= sz) for sz in range(lsz + 1)}
        self.max_size_map = {sz: frozenset(r for r in self if r.max_size >= sz) for sz in range(lsz + 1)}
        self.soak_routes = sorted(frozenset(r for r in self if r.soak_up_extra), key=attrgetter('min_size'), reverse=True)

    def find_route(self, path: tuple[str, ...]) -> tuple[RouteFunction, Iterator[object]]:
        if self.strip_path is not None and path[: len(self.strip_path)] == self.strip_path:
            path = path[len(self.strip_path) :]
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

    def read_cookies(self, data: RequestData) -> None:
        c: dict[str, str] = {}
        data.cookies = c

        for cval in data.inheaders.get('Cookie', all=True):
            if isinstance(cval, bytes):
                cval = cval.decode('utf-8', 'replace')
            for x in cval.split(';'):
                x = x.strip()
                if x:
                    k, v = x.partition('=')[::2]
                    if k:
                        # Since we only set simple hex encoded cookies, we don't
                        # need more sophisticated value parsing
                        c[k] = v.strip('"')

    def dispatch(self, data: RequestData) -> object:
        endpoint_, args = self.find_route(data.path)
        if data.method not in endpoint_.methods:
            raise HTTPSimpleResponse(http.client.METHOD_NOT_ALLOWED)

        self.read_cookies(data)

        if endpoint_.auth_required and self.auth_controller is not None:
            self.auth_controller(data, endpoint_)

        if endpoint_.ok_code is not None:
            data.status_code = endpoint_.ok_code

        self.init_session(endpoint_, data)
        if endpoint_.needs_db_write:
            assert self.ctx is not None
            self.ctx.check_for_write_access(data)
            data.needs_db_write = True
        # ctx is None only for routers created without a context, in tests
        ans = endpoint_(self.ctx, data, *args)  # ty: ignore[invalid-argument-type]
        self.finalize_session(endpoint_, data, ans)
        outheaders = data.outheaders

        pp = endpoint_.postprocess
        if pp is not None:
            ans = pp(self.ctx, data, endpoint_, ans)  # ty: ignore[invalid-argument-type]

        cc = endpoint_.cache_control
        if cc is not False and 'Cache-Control' not in data.outheaders:
            if cc is None or cc == 'no-cache':
                outheaders['Expires'] = http_date(10000.0)  # A date in the past
                outheaders['Cache-Control'] = 'no-cache, must-revalidate'
                outheaders['Pragma'] = 'no-cache'
            elif isinstance(cc, numbers.Number):
                cc = int(60 * 60 * cc)  # ty: ignore[invalid-argument-type]
                outheaders['Cache-Control'] = f'public, max-age={cc}'
                if cc == 0:
                    cc -= 100000
                outheaders['Expires'] = http_date(cc + time.time())
            else:
                ctype, max_age = cc  # ty: ignore[not-iterable]
                max_age = int(60 * 60 * max_age)
                outheaders['Cache-Control'] = f'{ctype}, max-age={max_age}'
                if max_age == 0:
                    max_age -= 100000
                outheaders['Expires'] = http_date(max_age + time.time())
        return ans

    def url_for(self, route: str | RouteFunction | None, **kwargs: object) -> str:
        if route is None:
            return self.url_prefix or '/'
        route = getattr(route, 'route_key', route)
        return self.url_prefix + self.routes[route].url_for(**kwargs)  # ty: ignore[invalid-argument-type]
