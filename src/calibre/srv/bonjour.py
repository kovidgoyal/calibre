#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from threading import Event
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from zeroconf import ServiceInfo

    from calibre.srv.loop import ServerLoop


class BonJour:  # {{{
    stop: Callable[[], None]

    def __init__(
        self,
        name: str = 'Books in calibre',
        service_type: str = '_calibre._tcp',
        path: str = '/opds',
        add_hostname: bool = True,
        wait_for_stop: bool | float = True,
    ) -> None:
        self.service_name = name
        self.wait_for_stop = wait_for_stop
        self.service_type = service_type
        self.add_hostname = add_hostname
        self.path = path
        self.shutdown = Event()
        self.stop = self.shutdown.set
        self.started = Event()
        self.stopped = Event()
        self.services: list[ServiceInfo] = []

    def start(self, loop: ServerLoop) -> None:
        from calibre.utils.mdns import publish, unpublish, verify_ip_address

        assert loop.bound_address is not None  # plugins are started only after the server socket is bound
        ip_address, port = loop.bound_address[:2]
        prefix = loop.opts.url_prefix or ''
        mdns_services = ((self.service_name, self.service_type, port, {'path': prefix + self.path}),)
        if self.shutdown.is_set():
            return
        self.services = []

        for s in mdns_services:
            si = publish(*s, add_hostname=self.add_hostname, use_ip_address=verify_ip_address(ip_address) or None)
            self.services.append(si)
            loop.log(f'OPDS feeds advertised via BonJour at: {", ".join(si.parsed_addresses())} port: {port}')
        self.advertised_port = port
        self.started.set()

        self.shutdown.wait()
        for s in mdns_services:
            unpublish(*s, add_hostname=self.add_hostname, wait_for_stop=self.wait_for_stop)
        self.stopped.set()


# }}}
