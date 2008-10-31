"""Site container for an HTTP server.

A Web Site Process Bus object is used to connect applications, servers,
and frameworks with site-wide services such as daemonization, process
reload, signal handling, drop privileges, PID file management, logging
for all of these, and many more.

The 'plugins' module defines a few abstract and concrete services for
use with the bus. Some use tool-specific channels; see the documentation
for each class.
"""

from cherrypy.process.wspbus import bus
from cherrypy.process import plugins, servers
