#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import unittest, pprint, threading, time

import cherrypy

from calibre import browser
from calibre.web.jsbrowser.browser import Browser
from calibre.library.server.utils import (cookie_max_age_to_expires,
        cookie_time_fmt)

class Server(object):

    def __init__(self):
        self.form_data = {}

    @cherrypy.expose
    def index(self):
        return '''
    <html>
    <head><title>JS Browser test</title></head>
    <script type="text/javascript" src="jquery"></script>
    <script type="text/javascript">
    $(document).ready(function() {
        $('#ajax_test').submit(function() {
            var val = $('#ajax_test input[name="text"]').val();
            $.ajax({
                dataType: "html",
                url: "/controls_test",
                data: {"text":val},
                success: function(data) {
                     $('#ajax_test input[name="text"]').val(data);
               }
            });
            return false;
        });
    });
    </script>

    <body>
    <form id="controls_test" method="post" action="controls_test">
        <h3>Test controls</h3>
        <div><label>Simple Text:</label><input type="text" name="text"/></div>
        <div><label>Password:</label><input type="password" name="password"/></div>
        <div><label>Checked Checkbox:</label><input type="checkbox" checked="checked" name="checked_checkbox"/></div>
        <div><label>UnChecked Checkbox:</label><input type="checkbox" name="unchecked_checkbox"/></div>
        <div><input type="radio" name="sex" value="male" checked="checked" /> Male</div>
        <div><input type="radio" name="sex" value="female" /> Female</div>
        <div><label>Color:</label><select name="color"><option value="red" selected="selected" /><option value="green" /></select></div>
        <div><input type="submit" value="Submit" /></div>
    </form>
    <form id="image_test" method="post" action="controls_test">
        <h3>Test Image submit</h3>
        <div><label>Simple Text:</label><input type="text" name="text" value="Image Test" /></div>
        <input type="image" src="button_image" alt="Submit" />
    </form>
    <form id="ajax_test" method="post" action="controls_test">
        <h3>Test AJAX submit</h3>
        <div><label>Simple Text:</label><input type="text" name="text" value="AJAX Test" /></div>
        <input type="submit" />
    </form>

    </body>
    </html>
    '''

    @cherrypy.expose
    def controls_test(self, **kwargs):
        self.form_data = kwargs.copy()
        #pprint.pprint(kwargs)
        return pprint.pformat(kwargs)

    @cherrypy.expose
    def button_image(self):
        cherrypy.response.headers['Content-Type'] = 'image/png'
        return I('next.png', data=True)

    @cherrypy.expose
    def jquery(self):
        cherrypy.response.headers['Content-Type'] = 'text/javascript'
        return P('content_server/jquery.js', data=True)

    @cherrypy.expose
    def cookies(self):
        try:
            cookie = cherrypy.response.cookie
            cookie[b'cookiea'] = 'The%20first%20cookie'
            cookie[b'cookiea']['path'] = '/'
            cookie[b'cookiea']['max-age'] = 60 # seconds
            cookie[b'cookieb'] = 'The_second_cookie'
            cookie[b'cookieb']['path'] = '/'
            cookie[b'cookieb']['expires'] = cookie_max_age_to_expires(60) # seconds
            cookie[b'cookiec'] = 'The_third_cookie'
            cookie[b'cookiec']['path'] = '/'
            self.sent_cookies = {n:(c.value, dict(c)) for n, c in
                    dict(cookie).iteritems()}
            return pprint.pformat(self.sent_cookies)
        except:
            import traceback
            traceback.print_exc()

    @cherrypy.expose
    def receive_cookies(self):
        self.received_cookies = {n:(c.value, dict(c)) for n, c in
                    dict(cherrypy.request.cookie).iteritems()}
        return pprint.pformat(self.received_cookies)

class Test(unittest.TestCase):

    @classmethod
    def run_server(cls):
        cherrypy.engine.start()
        try:
            cherrypy.engine.block()
        except:
            pass

    @classmethod
    def setUpClass(cls):
        cls.port = 17983
        cls.server = Server()
        cherrypy.config.update({
            'log.screen'             : False,
            'checker.on'             : False,
            'engine.autoreload_on'   : False,
            'request.show_tracebacks': True,
            'server.socket_host'     : b'127.0.0.1',
            'server.socket_port'     : cls.port,
            'server.socket_timeout'  : 10, #seconds
            'server.thread_pool'     : 5, # number of threads setting to 1 causes major slowdown
            'server.shutdown_timeout': 0.1, # minutes
        })
        cherrypy.tree.mount(cls.server, '/', config={'/':{}})

        cls.server_thread = threading.Thread(target=cls.run_server)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        cls.browser = Browser(verbosity=0)

    @classmethod
    def tearDownClass(cls):
        cherrypy.engine.exit()
        cls.browser = None

    def test_control_types(self):
        'Test setting data in the various control types'
        self.assertEqual(self.browser.visit('http://127.0.0.1:%d'%self.port),
                True)
        values = {
                'checked_checkbox'  : (False, None),
                'unchecked_checkbox': (True, 'on'),
                'text': ('some text', 'some text'),
                'password': ('some password', 'some password'),
                'sex': ('female', 'female'),
                'color': ('green', 'green'),
        }
        f = self.browser.select_form('#controls_test')
        for k, vals in values.iteritems():
            f[k] = vals[0]
        self.browser.submit()
        dat = self.server.form_data
        for k, vals in values.iteritems():
            self.assertEqual(vals[1], dat.get(k, None),
                    'Field %s: %r != %r'%(k, vals[1], dat.get(k, None)))

    def test_image_submit(self):
        'Test submitting a form with a image as the submit control'
        self.assertEqual(self.browser.visit('http://127.0.0.1:%d'%self.port),
                True)
        self.browser.select_form('#image_test')
        self.browser.submit()
        self.assertEqual(self.server.form_data['text'], 'Image Test')

    def test_ajax_submit(self):
        'Test AJAX based form submission'
        self.assertEqual(self.browser.visit('http://127.0.0.1:%d'%self.port),
                True)
        f = self.browser.select_form('#ajax_test')
        f['text'] = 'Changed'
        self.browser.ajax_submit()
        self.assertEqual(self.server.form_data['text'], 'Changed')

    def test_cookies(self):
        'Test migration of cookies to python objects'
        self.assertEqual(self.browser.visit('http://127.0.0.1:%d/cookies'%self.port),
                True)
        sent_cookies = self.server.sent_cookies
        cookies = self.browser.cookies
        cmap = {c.name:c for c in cookies}
        for name, vals in sent_cookies.iteritems():
            c = cmap[name]
            value, fields = vals
            self.assertEqual(value, c.value)
            for field in ('secure', 'path'):
                cval = getattr(c, field)
                if cval is False:
                    cval = b''
                self.assertEqual(fields[field], cval,
                        'Field %s in %s: %r != %r'%(field, name, fields[field], cval))
            cexp = cookie_time_fmt(time.gmtime(c.expires))
            fexp = fields['expires']
            if fexp:
                self.assertEqual(fexp, cexp)

    def test_cookie_copy(self):
        'Test copying of cookies from jsbrowser to mechanize'
        self.assertEqual(self.browser.visit('http://127.0.0.1:%d/cookies'%self.port),
                True)
        sent_cookies = self.server.sent_cookies.copy()
        self.browser.visit('http://127.0.0.1:%d/receive_cookies'%self.port)
        orig_rc = self.server.received_cookies.copy()
        br = browser(user_agent=self.browser.user_agent)
        br.copy_cookies_from_jsbrowser(self.browser)
        br.open('http://127.0.0.1:%d/receive_cookies'%self.port)
        for name, vals in sent_cookies.iteritems():
            val = vals[0]
            try:
                rval = self.server.received_cookies[name][0]
            except:
                self.fail('The cookie: %s was not received by the server')
            self.assertEqual(val, rval,
                'The received value for the cookie: %s, %s != %s'%(
                    name, rval, val))
        self.assertEqual(orig_rc, self.server.received_cookies)

def tests():
    return unittest.TestLoader().loadTestsFromTestCase(Test)

def run():
    unittest.TextTestRunner(verbosity=2).run(tests())

if __name__ == '__main__':
    run()

