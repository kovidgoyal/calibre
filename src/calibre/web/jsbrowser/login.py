#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre import USER_AGENT
from calibre.web.jsbrowser.browser import Browser

def do_login(login_url, calibre_browser, form_selector, controls={},
        num_of_replies=0, timeout=60.0, verbosity=0, pause_time=5,
        post_visit_callback=None, post_submit_callback=None,
        submit_control_selector=None):
    ua = USER_AGENT
    for key, val in calibre_browser.addheaders:
        if key.lower() == 'user-agent':
            ua = val
            break
    br = Browser(user_agent=ua, verbosity=verbosity)
    if not br.visit(login_url, timeout=timeout):
        raise ValueError('Failed to load the login URL: %r'%login_url)

    if callable(post_visit_callback):
        post_visit_callback(br)

    f = br.select_form(form_selector)
    for key, val in controls.iteritems():
        f[key] = val

    # br.show_browser()

    if num_of_replies > 0:
        br.ajax_submit(num_of_replies=num_of_replies, timeout=timeout,
                submit_control_selector=submit_control_selector)
    else:
        br.submit(timeout=timeout,
                submit_control_selector=submit_control_selector)

    # Give any javascript some time to run
    br.run_for_a_time(pause_time)

    if callable(post_submit_callback):
        post_submit_callback(br)

    br.show_browser()

    cj = calibre_browser.cookiejar
    for cookie in br.cookies:
        cj.set_cookie(cookie)
    html = br.html
    br.close()
    return html

