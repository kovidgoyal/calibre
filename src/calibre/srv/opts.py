#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple

Option = namedtuple('Option', 'name default doc choices')

raw_options = (

    'Path to the SSL certificate file',
    'ssl_certfile', None,

    'Path to the SSL private key file',
    'ssl_keyfile', None,

    ' Max. queued connections while waiting to accept',
    'request_queue_size', 5,

    'Timeout in seconds for accepted connections',
    'timeout', 10.0,

    'Total time in seconds to wait for worker threads to cleanly exit',
    'shutdown_timeout', 5.0,

    'Minimum number of connection handling threads',
    'min_threads', 10,

    'Maximum number of simultaneous connections (beyond this number of connections will be dropped)',
    'max_threads', 500,

    'Allow socket pre-allocation, for example, with systemd socket activation',
    'allow_socket_preallocation', True,

    'Max. size of single header (in KB)',
    'max_header_line_size', 8,

    'Max. size of a request (in MB)',
    'max_request_body_size', 500,

    'no_delay turns on TCP_NODELAY which decreases latency at the cost of'
    ' worse overall performance when sending multiple small packets. It'
    ' prevents the TCP stack from aggregating multiple small TCP packets.',
    'no_delay', True,
)

options = []

i = 0
while i + 2 < len(raw_options):
    doc, name, default = raw_options[i:i+3]
    i += 3
    choices = None
    if isinstance(default, set):
        default = list(default)[0]
        choices = raw_options[i]
        i += 1
    options.append(Option(name, default, doc, choices))
options = tuple(options)
del raw_options

defaults = namedtuple('Defaults', ' '.join(o.name for o in options))(*tuple(o.default for o in options))
