#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import subprocess, re
from calibre.constants import iswindows, ismacos


def get_address_of_default_gateway(family='AF_INET'):
    import netifaces
    ip = netifaces.gateways()['default'][getattr(netifaces, family)][0]
    if isinstance(ip, bytes):
        ip = ip.decode('ascii')
    return ip


def get_addresses_for_interface(name, family='AF_INET'):
    import netifaces
    for entry in netifaces.ifaddresses(name)[getattr(netifaces, family)]:
        if entry.get('broadcast'):  # Not a point-to-point address
            addr = entry.get('addr')
            if addr:
                if isinstance(addr, bytes):
                    addr = addr.decode('ascii')
                yield addr


if iswindows:

    def get_default_route_src_address_external():
        # Use -6 for IPv6 addresses
        raw = subprocess.check_output('route -4 print 0.0.0.0'.split(), creationflags=subprocess.DETACHED_PROCESS).decode('utf-8', 'replace')
        in_table = False
        default_gateway = get_address_of_default_gateway()
        for line in raw.splitlines():
            parts = line.strip().split()
            if in_table:
                if len(parts) == 6:
                    network, destination, netmask, gateway, interface, metric = parts
                elif len(parts) == 5:
                    destination, netmask, gateway, interface, metric = parts
                if gateway == default_gateway:
                    return interface
            else:
                if parts == 'Network Destination Netmask Gateway Interface Metric'.split():
                    in_table = True

    def get_default_route_src_address_api():
        from calibre.utils.iphlpapi import routes
        for route in routes():
            if route.interface and route.destination == '0.0.0.0':
                for addr in get_addresses_for_interface(route.interface):
                    return addr

    get_default_route_src_address = get_default_route_src_address_api


elif ismacos:

    def get_default_route_src_address():
        # Use -inet6 for IPv6
        raw = subprocess.check_output('route -n get -inet default'.split()).decode('utf-8')
        m = re.search(r'^\s*interface:\s*(\S+)\s*$', raw, flags=re.MULTILINE)
        if m is not None:
            interface = m.group(1)
            for addr in get_addresses_for_interface(interface):
                return addr
else:

    def get_default_route_src_address():
        # Use /proc/net/ipv6_route for IPv6 addresses
        with open('/proc/net/route', 'rb') as f:
            raw = f.read().decode('utf-8')
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) > 1 and parts[1] == '00000000':
                for addr in get_addresses_for_interface(parts[0]):
                    return addr

if __name__ == '__main__':
    print(get_default_route_src_address())
