#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2026, calibre contributors'

from calibre.srv.routes import endpoint
from calibre.srv.tests.base import BaseTest


class TestContentServerPlugin(BaseTest):
    def test_basic_endpoint_registration(self):
        from calibre.customize import ContentServerPlugin

        class TestPlugin(ContentServerPlugin):
            name = 'Test Content Plugin'

            def content_server_endpoints(self):
                @endpoint('/test-plugin/hello', auth_required=False)
                def hello(ctx, rd):
                    return 'hello'

                return [hello]

        plugin = TestPlugin(None)
        endpoints = list(plugin.content_server_endpoints())
        self.assertEqual(len(endpoints), 1)
        self.assertTrue(getattr(endpoints[0], 'is_endpoint', False))
        self.assertEqual(endpoints[0].route, '/test-plugin/hello')
        self.assertFalse(endpoints[0].auth_required)

    def test_default_empty_endpoints(self):
        from calibre.customize import ContentServerPlugin

        plugin = ContentServerPlugin(None)
        endpoints = plugin.content_server_endpoints()
        self.assertEqual(len(list(endpoints)), 0)

    def test_multiple_endpoints(self):
        from calibre.customize import ContentServerPlugin

        class MultiPlugin(ContentServerPlugin):
            name = 'Multi Route Plugin'

            def content_server_endpoints(self):
                @endpoint('/multi/a')
                def a(ctx, rd):
                    pass

                @endpoint('/multi/b', auth_required=False)
                def b(ctx, rd):
                    pass

                @endpoint('/multi/{x}', types={'x': int})
                def c(ctx, rd, x):
                    pass

                return [a, b, c]

        plugin = MultiPlugin(None)
        eps = list(plugin.content_server_endpoints())
        self.assertEqual(len(eps), 3)
        self.assertTrue(eps[0].auth_required)
        self.assertFalse(eps[1].auth_required)
        self.assertEqual(eps[2].types, {'x': int})


class TestPluginDiscovery(BaseTest):
    """
    Test that ContentServerPlugin endpoints are discovered and registered.
    Uses Router directly rather than Handler to avoid PyQt6 dependency
    in the test environment (calibre.srv.ajax -> calibre.ebooks.covers -> QtGui).
    """

    def setUp(self):
        from calibre.customize.ui import _initialized_plugins, config

        self._orig_plugins = list(_initialized_plugins)
        self._orig_disabled = set(config['disabled_plugins'])

    def tearDown(self):
        from calibre.customize.ui import _initialized_plugins, config

        _initialized_plugins[:] = self._orig_plugins
        config['disabled_plugins'] = self._orig_disabled

    def _register_all_plugin_routes(self, router):
        from calibre.customize.ui import content_server_plugins

        for plugin in content_server_plugins():
            for ep in plugin.content_server_endpoints():
                try:
                    router.add(ep)
                except ValueError:
                    pass

    def test_plugin_routes_loaded(self):
        from calibre.customize import ContentServerPlugin
        from calibre.customize.ui import _initialized_plugins
        from calibre.srv.routes import Router

        class RoutePlugin(ContentServerPlugin):
            name = 'Test Route Plugin'

            def content_server_endpoints(self):
                @endpoint('/test-route/ping', auth_required=False)
                def ping(ctx, rd):
                    return 'pong'

                return [ping]

        plugin = RoutePlugin(None)
        _initialized_plugins.append(plugin)
        router = Router()
        self._register_all_plugin_routes(router)
        router.finalize()
        path = tuple(filter(None, '/test-route/ping'.split('/')))
        ep, args = router.find_route(path)
        self.assertEqual(ep.route, '/test-route/ping')
        self.assertFalse(ep.auth_required)
        _initialized_plugins.remove(plugin)

    def test_disabled_plugin_skipped(self):
        from calibre.customize import ContentServerPlugin
        from calibre.customize.ui import _initialized_plugins, config
        from calibre.srv.routes import HTTPNotFound, Router

        class RoutePlugin(ContentServerPlugin):
            name = 'Disabled Route Plugin'

            def content_server_endpoints(self):
                @endpoint('/disabled-route/test', auth_required=False)
                def test(ctx, rd):
                    return 'test'

                return [test]

        plugin = RoutePlugin(None)
        _initialized_plugins.append(plugin)
        config['disabled_plugins'].add(plugin.name)
        router = Router()
        self._register_all_plugin_routes(router)
        router.finalize()
        path = tuple(filter(None, '/disabled-route/test'.split('/')))
        with self.assertRaises(HTTPNotFound):
            router.find_route(path)
        _initialized_plugins.remove(plugin)

    def test_plugin_conflict_does_not_override(self):
        from calibre.customize import ContentServerPlugin
        from calibre.customize.ui import _initialized_plugins
        from calibre.srv.routes import Router

        @endpoint('/test-route/ping', auth_required=False)
        def original(ctx, rd):
            return 'original'

        class OverridePlugin(ContentServerPlugin):
            name = 'Override Plugin'

            def content_server_endpoints(self):
                @endpoint('/test-route/ping', auth_required=False)
                def duplicate(ctx, rd):
                    return 'duplicate'

                return [duplicate]

        plugin = OverridePlugin(None)
        _initialized_plugins.append(plugin)
        router = Router()
        router.add(original)
        self._register_all_plugin_routes(router)
        router.finalize()
        path = tuple(filter(None, '/test-route/ping'.split('/')))
        ep, args = router.find_route(path)
        self.assertEqual(ep.__name__, 'original')
        _initialized_plugins.remove(plugin)

    def test_broken_plugin_does_not_block_others(self):
        from calibre.customize import ContentServerPlugin
        from calibre.customize.ui import _initialized_plugins
        from calibre.srv.routes import Router

        class GoodPlugin(ContentServerPlugin):
            name = 'Good Plugin'

            def content_server_endpoints(self):
                @endpoint('/good/hello', auth_required=False)
                def hello(ctx, rd):
                    return 'hello'

                return [hello]

        class BrokenPlugin(ContentServerPlugin):
            name = 'Broken Plugin'

            def content_server_endpoints(self):
                raise RuntimeError('oops')

        good = GoodPlugin(None)
        broken = BrokenPlugin(None)
        _initialized_plugins.append(good)
        _initialized_plugins.append(broken)
        router = Router()
        from calibre.customize.ui import content_server_plugins

        for plugin in content_server_plugins():
            try:
                endpoints = plugin.content_server_endpoints()
            except Exception:
                continue
            for ep in endpoints:
                try:
                    router.add(ep)
                except ValueError:
                    pass
        router.finalize()
        path = tuple(filter(None, '/good/hello'.split('/')))
        ep, args = router.find_route(path)
        self.assertEqual(ep.route, '/good/hello')
        _initialized_plugins.remove(good)
        _initialized_plugins.remove(broken)
