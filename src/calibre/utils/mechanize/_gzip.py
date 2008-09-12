import urllib2
from cStringIO import StringIO
import _response

# GzipConsumer was taken from Fredrik Lundh's effbot.org-0.1-20041009 library
class GzipConsumer:

    def __init__(self, consumer):
        self.__consumer = consumer
        self.__decoder = None
        self.__data = ""

    def __getattr__(self, key):
        return getattr(self.__consumer, key)

    def feed(self, data):
        if self.__decoder is None:
            # check if we have a full gzip header
            data = self.__data + data
            try:
                i = 10
                flag = ord(data[3])
                if flag & 4: # extra
                    x = ord(data[i]) + 256*ord(data[i+1])
                    i = i + 2 + x
                if flag & 8: # filename
                    while ord(data[i]):
                        i = i + 1
                    i = i + 1
                if flag & 16: # comment
                    while ord(data[i]):
                        i = i + 1
                    i = i + 1
                if flag & 2: # crc
                    i = i + 2
                if len(data) < i:
                    raise IndexError("not enough data")
                if data[:3] != "\x1f\x8b\x08":
                    raise IOError("invalid gzip data")
                data = data[i:]
            except IndexError:
                self.__data = data
                return # need more data
            import zlib
            self.__data = ""
            self.__decoder = zlib.decompressobj(-zlib.MAX_WBITS)
        data = self.__decoder.decompress(data)
        if data:
            self.__consumer.feed(data)

    def close(self):
        if self.__decoder:
            data = self.__decoder.flush()
            if data:
                self.__consumer.feed(data)
        self.__consumer.close()


# --------------------------------------------------------------------

# the rest of this module is John Lee's stupid code, not
# Fredrik's nice code :-)

class stupid_gzip_consumer:
    def __init__(self): self.data = []
    def feed(self, data): self.data.append(data)

class stupid_gzip_wrapper(_response.closeable_response):
    def __init__(self, response):
        self._response = response

        c = stupid_gzip_consumer()
        gzc = GzipConsumer(c)
        gzc.feed(response.read())
        self.__data = StringIO("".join(c.data))

    def read(self, size=-1):
        return self.__data.read(size)
    def readline(self, size=-1):
        return self.__data.readline(size)
    def readlines(self, sizehint=-1):
        return self.__data.readlines(size)

    def __getattr__(self, name):
        # delegate unknown methods/attributes
        return getattr(self._response, name)

class HTTPGzipProcessor(urllib2.BaseHandler):
    handler_order = 200  # response processing before HTTPEquivProcessor

    def http_request(self, request):
        request.add_header("Accept-Encoding", "gzip")
        return request

    def http_response(self, request, response):
        # post-process response
        enc_hdrs = response.info().getheaders("Content-encoding")
        for enc_hdr in enc_hdrs:
            if ("gzip" in enc_hdr) or ("compress" in enc_hdr):
                return stupid_gzip_wrapper(response)
        return response

    https_response = http_response
