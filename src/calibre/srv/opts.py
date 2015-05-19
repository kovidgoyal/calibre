#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple, OrderedDict
from operator import attrgetter

Option = namedtuple('Option', 'name default longdoc shortdoc choices')

class Choices(frozenset):
    def __new__(cls, *args):
        self = super(Choices, cls).__new__(cls, args)
        self.default = args[0]
        return self

raw_options = (

    'Path to the SSL certificate file',
    'ssl_certfile', None,
    None,

    'Path to the SSL private key file',
    'ssl_keyfile', None,
    None,

    'Max. queued connections while waiting to accept',
    'request_queue_size', 5,
    None,

    'Timeout in seconds for accepted connections',
    'timeout', 10.0,
    None,

    'Total time in seconds to wait for clean shutdown',
    'shutdown_timeout', 5.0,
    None,

    'Minimum number of connection handling threads',
    'min_threads', 10,
    None,

    'Maximum number of simultaneous connections (beyond this number of connections will be dropped)',
    'max_threads', 500,
    None,

    'Allow socket pre-allocation, for example, with systemd socket activation',
    'allow_socket_preallocation', True,
    None,

    'Max. size of single HTTP header (in KB)',
    'max_header_line_size', 8,
    None,

    'Max. size of a HTTP request (in MB)',
    'max_request_body_size', 500,
    None,

    'Decrease latency by using the TCP_NODELAY feature',
    'no_delay', True,
    'no_delay turns on TCP_NODELAY which decreases latency at the cost of'
    ' worse overall performance when sending multiple small packets. It'
    ' prevents the TCP stack from aggregating multiple small TCP packets.',
)

options = []

i = 0
while i + 3 < len(raw_options):
    shortdoc, name, default, doc = raw_options[i:i+4]
    i += 4
    choices = None
    if isinstance(default, Choices):
        choices = default
        default = default.default
    options.append(Option(name, default, doc, shortdoc, choices))
options = OrderedDict([(o.name, o) for o in sorted(options, key=attrgetter('name'))])
del raw_options

class Options(object):

    __slots__ = tuple(name for name in options)

    def __init__(self, **kwargs):
        for opt in options.itervalues():
            setattr(self, opt.name, kwargs.get(opt.name, opt.default))
