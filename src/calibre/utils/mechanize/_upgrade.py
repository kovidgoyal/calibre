from urllib2 import BaseHandler

from _request import Request
from _response import upgrade_response
from _util import deprecation


class HTTPRequestUpgradeProcessor(BaseHandler):
    # upgrade urllib2.Request to this module's Request
    # yuck!
    handler_order = 0  # before anything else

    def http_request(self, request):
        if not hasattr(request, "add_unredirected_header"):
            newrequest = Request(request._Request__original, request.data,
                                 request.headers)
            try: newrequest.origin_req_host = request.origin_req_host
            except AttributeError: pass
            try: newrequest.unverifiable = request.unverifiable
            except AttributeError: pass
            try: newrequest.visit = request.visit
            except AttributeError: pass
            request = newrequest
        return request

    https_request = http_request


class ResponseUpgradeProcessor(BaseHandler):
    # upgrade responses to be .close()able without becoming unusable
    handler_order = 0  # before anything else

    def __init__(self):
        deprecation(
            "See http://wwwsearch.sourceforge.net/mechanize/doc.html#seekable")

    def any_response(self, request, response):
        if not hasattr(response, 'closeable_response'):
            response = upgrade_response(response)
        return response
