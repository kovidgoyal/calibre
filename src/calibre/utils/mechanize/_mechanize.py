"""Stateful programmatic WWW navigation, after Perl's WWW::Mechanize.

Copyright 2003-2006 John J. Lee <jjl@pobox.com>
Copyright 2003 Andy Lester (original Perl code)

This code is free software; you can redistribute it and/or modify it
under the terms of the BSD or ZPL 2.1 licenses (see the file COPYING.txt
included with the distribution).

"""

import urllib2, sys, copy, re

from _useragent import UserAgentBase
from _html import DefaultFactory
import _response
import _request
import _rfc3986

__version__ = (0, 1, 7, "b", None)  # 0.1.7b

class BrowserStateError(Exception): pass
class LinkNotFoundError(Exception): pass
class FormNotFoundError(Exception): pass


class History:
    """

    Though this will become public, the implied interface is not yet stable.

    """
    def __init__(self):
        self._history = []  # LIFO
    def add(self, request, response):
        self._history.append((request, response))
    def back(self, n, _response):
        response = _response  # XXX move Browser._response into this class?
        while n > 0 or response is None:
            try:
                request, response = self._history.pop()
            except IndexError:
                raise BrowserStateError("already at start of history")
            n -= 1
        return request, response
    def clear(self):
        del self._history[:]
    def close(self):
        for request, response in self._history:
            if response is not None:
                response.close()
        del self._history[:]


class HTTPRefererProcessor(urllib2.BaseHandler):
    def http_request(self, request):
        # See RFC 2616 14.36.  The only times we know the source of the
        # request URI has a URI associated with it are redirect, and
        # Browser.click() / Browser.submit() / Browser.follow_link().
        # Otherwise, it's the user's job to add any Referer header before
        # .open()ing.
        if hasattr(request, "redirect_dict"):
            request = self.parent._add_referer_header(
                request, origin_request=False)
        return request

    https_request = http_request


class Browser(UserAgentBase):
    """Browser-like class with support for history, forms and links.

    BrowserStateError is raised whenever the browser is in the wrong state to
    complete the requested operation - eg., when .back() is called when the
    browser history is empty, or when .follow_link() is called when the current
    response does not contain HTML data.

    Public attributes:

    request: current request (mechanize.Request or urllib2.Request)
    form: currently selected form (see .select_form())

    """

    handler_classes = copy.copy(UserAgentBase.handler_classes)
    handler_classes["_referer"] = HTTPRefererProcessor
    default_features = copy.copy(UserAgentBase.default_features)
    default_features.append("_referer")

    def __init__(self,
                 factory=None,
                 history=None,
                 request_class=None,
                 ):
        """

        Only named arguments should be passed to this constructor.

        factory: object implementing the mechanize.Factory interface.
        history: object implementing the mechanize.History interface.  Note
         this interface is still experimental and may change in future.
        request_class: Request class to use.  Defaults to mechanize.Request
         by default for Pythons older than 2.4, urllib2.Request otherwise.

        The Factory and History objects passed in are 'owned' by the Browser,
        so they should not be shared across Browsers.  In particular,
        factory.set_response() should not be called except by the owning
        Browser itself.

        Note that the supplied factory's request_class is overridden by this
        constructor, to ensure only one Request class is used.

        """
        self._handle_referer = True

        if history is None:
            history = History()
        self._history = history

        if request_class is None:
            if not hasattr(urllib2.Request, "add_unredirected_header"):
                request_class = _request.Request
            else:
                request_class = urllib2.Request  # Python >= 2.4

        if factory is None:
            factory = DefaultFactory()
        factory.set_request_class(request_class)
        self._factory = factory
        self.request_class = request_class

        self.request = None
        self._set_response(None, False)

        # do this last to avoid __getattr__ problems
        UserAgentBase.__init__(self)

    def close(self):
        UserAgentBase.close(self)
        if self._response is not None:
            self._response.close()    
        if self._history is not None:
            self._history.close()
            self._history = None

        # make use after .close easy to spot
        self.form = None
        self.request = self._response = None
        self.request = self.response = self.set_response = None
        self.geturl =  self.reload = self.back = None
        self.clear_history = self.set_cookie = self.links = self.forms = None
        self.viewing_html = self.encoding = self.title = None
        self.select_form = self.click = self.submit = self.click_link = None
        self.follow_link = self.find_link = None

    def set_handle_referer(self, handle):
        """Set whether to add Referer header to each request.

        This base class does not implement this feature (so don't turn this on
        if you're using this base class directly), but the subclass
        mechanize.Browser does.

        """
        self._set_handler("_referer", handle)
        self._handle_referer = bool(handle)

    def _add_referer_header(self, request, origin_request=True):
        if self.request is None:
            return request
        scheme = request.get_type()
        original_scheme = self.request.get_type()
        if scheme not in ["http", "https"]:
            return request
        if not origin_request and not self.request.has_header("Referer"):
            return request

        if (self._handle_referer and
            original_scheme in ["http", "https"] and
            not (original_scheme == "https" and scheme != "https")):
            # strip URL fragment (RFC 2616 14.36)
            parts = _rfc3986.urlsplit(self.request.get_full_url())
            parts = parts[:-1]+(None,)
            referer = _rfc3986.urlunsplit(parts)
            request.add_unredirected_header("Referer", referer)
        return request

    def open_novisit(self, url, data=None):
        """Open a URL without visiting it.

        The browser state (including .request, .response(), history, forms and
        links) are all left unchanged by calling this function.

        The interface is the same as for .open().

        This is useful for things like fetching images.

        See also .retrieve().

        """
        return self._mech_open(url, data, visit=False)

    def open(self, url, data=None):
        return self._mech_open(url, data)

    def _mech_open(self, url, data=None, update_history=True, visit=None):
        try:
            url.get_full_url
        except AttributeError:
            # string URL -- convert to absolute URL if required
            scheme, authority = _rfc3986.urlsplit(url)[:2]
            if scheme is None:
                # relative URL
                if self._response is None:
                    raise BrowserStateError(
                        "can't fetch relative reference: "
                        "not viewing any document")
                url = _rfc3986.urljoin(self._response.geturl(), url)

        request = self._request(url, data, visit)
        visit = request.visit
        if visit is None:
            visit = True

        if visit:
            self._visit_request(request, update_history)

        success = True
        try:
            response = UserAgentBase.open(self, request, data)
        except urllib2.HTTPError, error:
            success = False
            if error.fp is None:  # not a response
                raise
            response = error
##         except (IOError, socket.error, OSError), error:
##             # Yes, urllib2 really does raise all these :-((
##             # See test_urllib2.py for examples of socket.gaierror and OSError,
##             # plus note that FTPHandler raises IOError.
##             # XXX I don't seem to have an example of exactly socket.error being
##             #  raised, only socket.gaierror...
##             # I don't want to start fixing these here, though, since this is a
##             # subclass of OpenerDirector, and it would break old code.  Even in
##             # Python core, a fix would need some backwards-compat. hack to be
##             # acceptable.
##             raise

        if visit:
            self._set_response(response, False)
            response = copy.copy(self._response)
        elif response is not None:
            response = _response.upgrade_response(response)

        if not success:
            raise response
        return response

    def __str__(self):
        text = []
        text.append("<%s " % self.__class__.__name__)
        if self._response:
            text.append("visiting %s" % self._response.geturl())
        else:
            text.append("(not visiting a URL)")
        if self.form:
            text.append("\n selected form:\n %s\n" % str(self.form))
        text.append(">")
        return "".join(text)

    def response(self):
        """Return a copy of the current response.

        The returned object has the same interface as the object returned by
        .open() (or urllib2.urlopen()).

        """
        return copy.copy(self._response)

    def set_response(self, response):
        """Replace current response with (a copy of) response.

        response may be None.

        This is intended mostly for HTML-preprocessing.
        """
        self._set_response(response, True)

    def _set_response(self, response, close_current):
        # sanity check, necessary but far from sufficient
        if not (response is None or
                (hasattr(response, "info") and hasattr(response, "geturl") and
                 hasattr(response, "read")
                 )
                ):
            raise ValueError("not a response object")

        self.form = None
        if response is not None:
            response = _response.upgrade_response(response)
        if close_current and self._response is not None:
            self._response.close()
        self._response = response
        self._factory.set_response(response)

    def visit_response(self, response, request=None):
        """Visit the response, as if it had been .open()ed.

        Unlike .set_response(), this updates history rather than replacing the
        current response.
        """
        if request is None:
            request = _request.Request(response.geturl())
        self._visit_request(request, True)
        self._set_response(response, False)

    def _visit_request(self, request, update_history):
        if self._response is not None:
            self._response.close()
        if self.request is not None and update_history:
            self._history.add(self.request, self._response)
        self._response = None
        # we want self.request to be assigned even if UserAgentBase.open
        # fails
        self.request = request

    def geturl(self):
        """Get URL of current document."""
        if self._response is None:
            raise BrowserStateError("not viewing any document")
        return self._response.geturl()

    def reload(self):
        """Reload current document, and return response object."""
        if self.request is None:
            raise BrowserStateError("no URL has yet been .open()ed")
        if self._response is not None:
            self._response.close()
        return self._mech_open(self.request, update_history=False)

    def back(self, n=1):
        """Go back n steps in history, and return response object.

        n: go back this number of steps (default 1 step)

        """
        if self._response is not None:
            self._response.close()
        self.request, response = self._history.back(n, self._response)
        self.set_response(response)
        if not response.read_complete:
            return self.reload()
        return copy.copy(response)

    def clear_history(self):
        self._history.clear()

    def set_cookie(self, cookie_string):
        """Request to set a cookie.

        Note that it is NOT necessary to call this method under ordinary
        circumstances: cookie handling is normally entirely automatic.  The
        intended use case is rather to simulate the setting of a cookie by
        client script in a web page (e.g. JavaScript).  In that case, use of
        this method is necessary because mechanize currently does not support
        JavaScript, VBScript, etc.

        The cookie is added in the same way as if it had arrived with the
        current response, as a result of the current request.  This means that,
        for example, it is not appropriate to set the cookie based on the
        current request, no cookie will be set.

        The cookie will be returned automatically with subsequent responses
        made by the Browser instance whenever that's appropriate.

        cookie_string should be a valid value of the Set-Cookie header.

        For example:

        browser.set_cookie(
            "sid=abcdef; expires=Wednesday, 09-Nov-06 23:12:40 GMT")

        Currently, this method does not allow for adding RFC 2986 cookies.
        This limitation will be lifted if anybody requests it.

        """
        if self._response is None:
            raise BrowserStateError("not viewing any document")
        if self.request.get_type() not in ["http", "https"]:
            raise BrowserStateError("can't set cookie for non-HTTP/HTTPS "
                                    "transactions")
        cookiejar = self._ua_handlers["_cookies"].cookiejar
        response = self.response()  # copy
        headers = response.info()
        headers["Set-cookie"] = cookie_string
        cookiejar.extract_cookies(response, self.request)

    def links(self, **kwds):
        """Return iterable over links (mechanize.Link objects)."""
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        links = self._factory.links()
        if kwds:
            return self._filter_links(links, **kwds)
        else:
            return links

    def forms(self):
        """Return iterable over forms.

        The returned form objects implement the ClientForm.HTMLForm interface.

        """
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        return self._factory.forms()

    def global_form(self):
        """Return the global form object, or None if the factory implementation
        did not supply one.

        The "global" form object contains all controls that are not descendants of
        any FORM element.

        The returned form object implements the ClientForm.HTMLForm interface.

        This is a separate method since the global form is not regarded as part
        of the sequence of forms in the document -- mostly for
        backwards-compatibility.

        """
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        return self._factory.global_form

    def viewing_html(self):
        """Return whether the current response contains HTML data."""
        if self._response is None:
            raise BrowserStateError("not viewing any document")
        return self._factory.is_html

    def encoding(self):
        """"""
        if self._response is None:
            raise BrowserStateError("not viewing any document")
        return self._factory.encoding

    def title(self):
        """Return title, or None if there is no title element in the document.

        Tags are stripped or textified as described in docs for
        PullParser.get_text() method of pullparser module.

        """
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        return self._factory.title

    def select_form(self, name=None, predicate=None, nr=None):
        """Select an HTML form for input.

        This is a bit like giving a form the "input focus" in a browser.

        If a form is selected, the Browser object supports the HTMLForm
        interface, so you can call methods like .set_value(), .set(), and
        .click().

        Another way to select a form is to assign to the .form attribute.  The
        form assigned should be one of the objects returned by the .forms()
        method.

        At least one of the name, predicate and nr arguments must be supplied.
        If no matching form is found, mechanize.FormNotFoundError is raised.

        If name is specified, then the form must have the indicated name.

        If predicate is specified, then the form must match that function.  The
        predicate function is passed the HTMLForm as its single argument, and
        should return a boolean value indicating whether the form matched.

        nr, if supplied, is the sequence number of the form (where 0 is the
        first).  Note that control 0 is the first form matching all the other
        arguments (if supplied); it is not necessarily the first control in the
        form.

        """
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        if (name is None) and (predicate is None) and (nr is None):
            raise ValueError(
                "at least one argument must be supplied to specify form")

        orig_nr = nr
        for form in self.forms():
            if name is not None and name != form.name:
                continue
            if predicate is not None and not predicate(form):
                continue
            if nr:
                nr -= 1
                continue
            self.form = form
            break  # success
        else:
            # failure
            description = []
            if name is not None: description.append("name '%s'" % name)
            if predicate is not None:
                description.append("predicate %s" % predicate)
            if orig_nr is not None: description.append("nr %d" % orig_nr)
            description = ", ".join(description)
            raise FormNotFoundError("no form matching "+description)

    def click(self, *args, **kwds):
        """See ClientForm.HTMLForm.click for documentation."""
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        request = self.form.click(*args, **kwds)
        return self._add_referer_header(request)

    def submit(self, *args, **kwds):
        """Submit current form.

        Arguments are as for ClientForm.HTMLForm.click().

        Return value is same as for Browser.open().

        """
        return self.open(self.click(*args, **kwds))

    def click_link(self, link=None, **kwds):
        """Find a link and return a Request object for it.

        Arguments are as for .find_link(), except that a link may be supplied
        as the first argument.

        """
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")
        if not link:
            link = self.find_link(**kwds)
        else:
            if kwds:
                raise ValueError(
                    "either pass a Link, or keyword arguments, not both")
        request = self.request_class(link.absolute_url)
        return self._add_referer_header(request)

    def follow_link(self, link=None, **kwds):
        """Find a link and .open() it.

        Arguments are as for .click_link().

        Return value is same as for Browser.open().

        """
        return self.open(self.click_link(link, **kwds))

    def find_link(self, **kwds):
        """Find a link in current page.

        Links are returned as mechanize.Link objects.

        # Return third link that .search()-matches the regexp "python"
        # (by ".search()-matches", I mean that the regular expression method
        # .search() is used, rather than .match()).
        find_link(text_regex=re.compile("python"), nr=2)

        # Return first http link in the current page that points to somewhere
        # on python.org whose link text (after tags have been removed) is
        # exactly "monty python".
        find_link(text="monty python",
                  url_regex=re.compile("http.*python.org"))

        # Return first link with exactly three HTML attributes.
        find_link(predicate=lambda link: len(link.attrs) == 3)

        Links include anchors (<a>), image maps (<area>), and frames (<frame>,
        <iframe>).

        All arguments must be passed by keyword, not position.  Zero or more
        arguments may be supplied.  In order to find a link, all arguments
        supplied must match.

        If a matching link is not found, mechanize.LinkNotFoundError is raised.

        text: link text between link tags: eg. <a href="blah">this bit</a> (as
         returned by pullparser.get_compressed_text(), ie. without tags but
         with opening tags "textified" as per the pullparser docs) must compare
         equal to this argument, if supplied
        text_regex: link text between tag (as defined above) must match the
         regular expression object or regular expression string passed as this
         argument, if supplied
        name, name_regex: as for text and text_regex, but matched against the
         name HTML attribute of the link tag
        url, url_regex: as for text and text_regex, but matched against the
         URL of the link tag (note this matches against Link.url, which is a
         relative or absolute URL according to how it was written in the HTML)
        tag: element name of opening tag, eg. "a"
        predicate: a function taking a Link object as its single argument,
         returning a boolean result, indicating whether the links
        nr: matches the nth link that matches all other criteria (default 0)

        """
        try:
            return self._filter_links(self._factory.links(), **kwds).next()
        except StopIteration:
            raise LinkNotFoundError()

    def __getattr__(self, name):
        # pass through ClientForm / DOMForm methods and attributes
        form = self.__dict__.get("form")
        if form is None:
            raise AttributeError(
                "%s instance has no attribute %s (perhaps you forgot to "
                ".select_form()?)" % (self.__class__, name))
        return getattr(form, name)

    def _filter_links(self, links,
                    text=None, text_regex=None,
                    name=None, name_regex=None,
                    url=None, url_regex=None,
                    tag=None,
                    predicate=None,
                    nr=0
                    ):
        if not self.viewing_html():
            raise BrowserStateError("not viewing HTML")

        found_links = []
        orig_nr = nr

        for link in links:
            if url is not None and url != link.url:
                continue
            if url_regex is not None and not re.search(url_regex, link.url):
                continue
            if (text is not None and
                (link.text is None or text != link.text)):
                continue
            if (text_regex is not None and
                (link.text is None or not re.search(text_regex, link.text))):
                continue
            if name is not None and name != dict(link.attrs).get("name"):
                continue
            if name_regex is not None:
                link_name = dict(link.attrs).get("name")
                if link_name is None or not re.search(name_regex, link_name):
                    continue
            if tag is not None and tag != link.tag:
                continue
            if predicate is not None and not predicate(link):
                continue
            if nr:
                nr -= 1
                continue
            yield link
            nr = orig_nr
