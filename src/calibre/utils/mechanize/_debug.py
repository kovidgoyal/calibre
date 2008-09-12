import logging

from urllib2 import BaseHandler
from _response import response_seek_wrapper


class HTTPResponseDebugProcessor(BaseHandler):
    handler_order = 900  # before redirections, after everything else

    def http_response(self, request, response):
        if not hasattr(response, "seek"):
            response = response_seek_wrapper(response)
        info = logging.getLogger("mechanize.http_responses").info
        try:
            info(response.read())
        finally:
            response.seek(0)
        info("*****************************************************")
        return response

    https_response = http_response

class HTTPRedirectDebugProcessor(BaseHandler):
    def http_request(self, request):
        if hasattr(request, "redirect_dict"):
            info = logging.getLogger("mechanize.http_redirects").info
            info("redirecting to %s", request.get_full_url())
        return request
