from urllib2 import BaseHandler
from _util import deprecation
from _response import response_seek_wrapper


class SeekableProcessor(BaseHandler):
    """Deprecated: Make responses seekable."""

    def __init__(self):
        deprecation(
            "See http://wwwsearch.sourceforge.net/mechanize/doc.html#seekable")

    def any_response(self, request, response):
        if not hasattr(response, "seek"):
            return response_seek_wrapper(response)
        return response
