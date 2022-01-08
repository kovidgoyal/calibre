#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Event


class BonJour:  # {{{

    def __init__(self, name='Books in calibre', service_type='_calibre._tcp', path='/opds', add_hostname=True, wait_for_stop=True):
        self.service_name = name
        self.wait_for_stop = wait_for_stop
        self.service_type = service_type
        self.add_hostname = add_hostname
        self.path = path
        self.shutdown = Event()
        self.stop = self.shutdown.set
        self.started = Event()
        self.stopped = Event()
        self.services = []

    def start(self, loop):
        from calibre.utils.mdns import publish, unpublish, get_external_ip, verify_ipV4_address
        ip_address, port = loop.bound_address[:2]
        self.zeroconf_ip_address = zipa = verify_ipV4_address(ip_address) or get_external_ip()
        prefix = loop.opts.url_prefix or ''
        mdns_services = (
            (self.service_name, self.service_type, port, {'path':prefix + self.path}),
        )
        if self.shutdown.is_set():
            return
        self.services = []

        for s in mdns_services:
            self.services.append(publish(*s, use_ip_address=zipa, add_hostname=self.add_hostname))
        loop.log(f'OPDS feeds advertised via BonJour at: {zipa} port: {port}')
        self.advertised_port = port
        self.started.set()

        self.shutdown.wait()
        for s in mdns_services:
            unpublish(*s, add_hostname=self.add_hostname, wait_for_stop=self.wait_for_stop)
        self.stopped.set()
# }}}
