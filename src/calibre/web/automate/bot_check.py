#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Wait out the interstitial page a bot check answers the first request with.

Several news sites, economist.com and nytimes.com among them, put an anti-bot
service in front of their pages. A browser the service has not scored yet is
answered with an interstitial rather than with the page that was asked for. The
interstitial arrives as an HTTP 403 while its own scripts, still running in the
tab, do the scoring and then reload the page, so a request that gets one is
simply made again, by which time the check has normally been passed once and for
all for the whole browser.

A recipe opts in from its ``get_browser()``::

    from calibre.web.automate.bot_check import retry_bot_checks

    class MyRecipe(BasicNewsRecipe):
        browser_type = 'camoufox'

        def get_browser(self, *args, **kwargs):
            return retry_bot_checks(BasicNewsRecipe.get_browser(self, *args, **kwargs))

Once only, in ``get_browser()``: every browser cloned from one that has been
through :func:`retry_bot_checks` retries as well, which matters because recipes
clone their browser once per article and a browser hands back clones of its own
class rather than of anything the recipe controls.
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.error import URLError

# The statuses an interstitial is served with: 403 is what the bot check itself
# answers with and 429 is what a service that thinks we are asking too often
# sends, which waiting a few seconds is also the right response to.
BOT_CHECK_STATUSES = frozenset({403, 429})
# Total attempts per request, so one original and the rest retries
BOT_CHECK_RETRIES = 4
BOT_CHECK_DELAY = 5  # seconds, long enough for the check's scripts to finish
# The methods of a browser that make a request
FETCH_METHODS = ('open', 'open_novisit')


def bot_check_retrier(fetch: Callable[..., Any], retries: int = BOT_CHECK_RETRIES, delay: float = BOT_CHECK_DELAY) -> Callable[..., Any]:
    """Wrap one of a browser's fetching methods to wait out the bot check.

    Only the statuses in :data:`BOT_CHECK_STATUSES` are retried, and the last
    attempt is made outside the loop so that whatever it raises reaches the
    caller unchanged rather than being turned into an error of our own.
    """

    @wraps(fetch)
    def retrying(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        for _ in range(retries - 1):
            try:
                return fetch(*args, **kwargs)
            except URLError as err:
                if getattr(err, 'code', None) not in BOT_CHECK_STATUSES:
                    raise
                time.sleep(delay)
        return fetch(*args, **kwargs)

    return retrying


def retry_bot_checks[B](br: B, retries: int = BOT_CHECK_RETRIES, delay: float = BOT_CHECK_DELAY) -> B:
    """Make br, and every browser cloned from it, retry the bot check.

    The methods are wrapped on the instance rather than in a subclass because a
    browser's ``clone_browser()`` hands back an object of its own class, which a
    recipe has no say over. Wrapping that method too is what carries the
    behaviour into the clones the download threads use.
    """
    if getattr(br, 'retries_bot_checks', False):
        return br
    for name in FETCH_METHODS:
        setattr(br, name, bot_check_retrier(getattr(br, name), retries, delay))
    clone = getattr(br, 'clone_browser', None)
    if callable(clone):

        @wraps(clone)
        def cloning(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            return retry_bot_checks(clone(*args, **kwargs), retries, delay)

        setattr(br, 'clone_browser', cloning)
    setattr(br, 'retries_bot_checks', True)
    return br
