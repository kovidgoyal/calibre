#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import ctypes
from ctypes import windll
from ctypes import wintypes
from collections import namedtuple
from contextlib import contextmanager

# Wraps (part of) the IPHelper API, useful to enumerate the network routes and
# adapters on the local machine


class GUID(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", wintypes.BYTE * 8)]

    def __init__(self, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8):
        self.data1 = l
        self.data2 = w1
        self.data3 = w2
        self.data4[0] = b1
        self.data4[1] = b2
        self.data4[2] = b3
        self.data4[3] = b4
        self.data4[4] = b5
        self.data4[5] = b6
        self.data4[6] = b7
        self.data4[7] = b8


class SOCKADDR(ctypes.Structure):
    _fields_ = [
        ('sa_family', wintypes.USHORT),
        ('sa_data', ctypes.c_char * 14),
    ]


ERROR_SUCCESS = 0
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_BUFFER_OVERFLOW = 111
MAX_ADAPTER_NAME_LENGTH = 256
MAX_ADAPTER_DESCRIPTION_LENGTH = 128
MAX_ADAPTER_ADDRESS_LENGTH = 8

# Do not return IPv6 anycast addresses.
GAA_FLAG_SKIP_ANYCAST = 2
GAA_FLAG_SKIP_MULTICAST = 4

IP_ADAPTER_DHCP_ENABLED = 4
IP_ADAPTER_IPV4_ENABLED = 0x80
IP_ADAPTER_IPV6_ENABLED = 0x0100

MAX_DHCPV6_DUID_LENGTH = 130

IF_TYPE_ETHERNET_CSMACD = 6
IF_TYPE_SOFTWARE_LOOPBACK = 24
IF_TYPE_IEEE80211 = 71
IF_TYPE_TUNNEL = 131

IP_ADAPTER_ADDRESSES_SIZE_2003 = 144


class SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [
        ('lpSockaddr', ctypes.POINTER(SOCKADDR)),
        ('iSockaddrLength', wintypes.INT),
    ]


class IP_ADAPTER_ADDRESSES_Struct1(ctypes.Structure):
    _fields_ = [
        ('Length', wintypes.ULONG),
        ('IfIndex', wintypes.DWORD),
    ]


class IP_ADAPTER_ADDRESSES_Union1(ctypes.Union):
    _fields_ = [
        ('Alignment', wintypes.ULARGE_INTEGER),
        ('Struct1', IP_ADAPTER_ADDRESSES_Struct1),
    ]


class IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
    _fields_ = [
        ('Union1', IP_ADAPTER_ADDRESSES_Union1),
        ('Next', wintypes.LPVOID),
        ('Address', SOCKET_ADDRESS),
        ('PrefixOrigin', wintypes.DWORD),
        ('SuffixOrigin', wintypes.DWORD),
        ('DadState', wintypes.DWORD),
        ('ValidLifetime', wintypes.ULONG),
        ('PreferredLifetime', wintypes.ULONG),
        ('LeaseLifetime', wintypes.ULONG),
    ]


class IP_ADAPTER_DNS_SERVER_ADDRESS_Struct1(ctypes.Structure):
    _fields_ = [
        ('Length', wintypes.ULONG),
        ('Reserved', wintypes.DWORD),
    ]


class IP_ADAPTER_DNS_SERVER_ADDRESS_Union1(ctypes.Union):
    _fields_ = [
        ('Alignment', wintypes.ULARGE_INTEGER),
        ('Struct1', IP_ADAPTER_DNS_SERVER_ADDRESS_Struct1),
    ]


class IP_ADAPTER_DNS_SERVER_ADDRESS(ctypes.Structure):
    _fields_ = [
        ('Union1', IP_ADAPTER_DNS_SERVER_ADDRESS_Union1),
        ('Next', wintypes.LPVOID),
        ('Address', SOCKET_ADDRESS),
    ]


class IP_ADAPTER_PREFIX_Struct1(ctypes.Structure):
    _fields_ = [
        ('Length', wintypes.ULONG),
        ('Flags', wintypes.DWORD),
    ]


class IP_ADAPTER_PREFIX_Union1(ctypes.Union):
    _fields_ = [
        ('Alignment', wintypes.ULARGE_INTEGER),
        ('Struct1', IP_ADAPTER_PREFIX_Struct1),
    ]


class IP_ADAPTER_PREFIX(ctypes.Structure):
    _fields_ = [
        ('Union1', IP_ADAPTER_PREFIX_Union1),
        ('Next', wintypes.LPVOID),
        ('Address', SOCKET_ADDRESS),
        ('PrefixLength', wintypes.ULONG),
    ]


class IP_ADAPTER_DNS_SUFFIX(ctypes.Structure):
    _fields_ = [
        ('Next', wintypes.LPVOID),
        ('String', wintypes.LPWSTR),
    ]


class NET_LUID_LH(ctypes.Union):
    _fields_ = [
        ('Value', wintypes.ULARGE_INTEGER),
        ('Info', wintypes.ULARGE_INTEGER),
    ]


class IP_ADAPTER_ADDRESSES(ctypes.Structure):
    _fields_ = [
        ('Union1', IP_ADAPTER_ADDRESSES_Union1),
        ('Next', wintypes.LPVOID),
        ('AdapterName', ctypes.c_char_p),
        ('FirstUnicastAddress',
         ctypes.POINTER(IP_ADAPTER_UNICAST_ADDRESS)),
        ('FirstAnycastAddress',
         ctypes.POINTER(IP_ADAPTER_DNS_SERVER_ADDRESS)),
        ('FirstMulticastAddress',
         ctypes.POINTER(IP_ADAPTER_DNS_SERVER_ADDRESS)),
        ('FirstDnsServerAddress',
         ctypes.POINTER(IP_ADAPTER_DNS_SERVER_ADDRESS)),
        ('DnsSuffix', wintypes.LPWSTR),
        ('Description', wintypes.LPWSTR),
        ('FriendlyName', wintypes.LPWSTR),
        ('PhysicalAddress', ctypes.c_ubyte * MAX_ADAPTER_ADDRESS_LENGTH),
        ('PhysicalAddressLength', wintypes.DWORD),
        ('Flags', wintypes.DWORD),
        ('Mtu', wintypes.DWORD),
        ('IfType', wintypes.DWORD),
        ('OperStatus', wintypes.DWORD),
        ('Ipv6IfIndex', wintypes.DWORD),
        ('ZoneIndices', wintypes.DWORD * 16),
        ('FirstPrefix', ctypes.POINTER(IP_ADAPTER_PREFIX)),
        # Vista and later
        ('TransmitLinkSpeed', wintypes.ULARGE_INTEGER),
        ('ReceiveLinkSpeed', wintypes.ULARGE_INTEGER),
        ('FirstWinsServerAddress',
         ctypes.POINTER(IP_ADAPTER_DNS_SERVER_ADDRESS)),
        ('FirstGatewayAddress',
         ctypes.POINTER(IP_ADAPTER_DNS_SERVER_ADDRESS)),
        ('Ipv4Metric', wintypes.ULONG),
        ('Ipv6Metric', wintypes.ULONG),
        ('Luid', NET_LUID_LH),
        ('Dhcpv4Server', SOCKET_ADDRESS),
        ('CompartmentId', wintypes.DWORD),
        ('NetworkGuid', GUID),
        ('ConnectionType', wintypes.DWORD),
        ('TunnelType', wintypes.DWORD),
        ('Dhcpv6Server', SOCKET_ADDRESS),
        ('Dhcpv6ClientDuid', ctypes.c_ubyte * MAX_DHCPV6_DUID_LENGTH),
        ('Dhcpv6ClientDuidLength', wintypes.ULONG),
        ('Dhcpv6Iaid', wintypes.ULONG),
        # Vista SP1 and later, so we comment it out as we dont need it
        # ('FirstDnsSuffix', ctypes.POINTER(IP_ADAPTER_DNS_SUFFIX)),
    ]


class Win32_MIB_IPFORWARDROW(ctypes.Structure):
    _fields_ = [
        ('dwForwardDest', wintypes.DWORD),
        ('dwForwardMask', wintypes.DWORD),
        ('dwForwardPolicy', wintypes.DWORD),
        ('dwForwardNextHop', wintypes.DWORD),
        ('dwForwardIfIndex', wintypes.DWORD),
        ('dwForwardType', wintypes.DWORD),
        ('dwForwardProto', wintypes.DWORD),
        ('dwForwardAge', wintypes.DWORD),
        ('dwForwardNextHopAS', wintypes.DWORD),
        ('dwForwardMetric1', wintypes.DWORD),
        ('dwForwardMetric2', wintypes.DWORD),
        ('dwForwardMetric3', wintypes.DWORD),
        ('dwForwardMetric4', wintypes.DWORD),
        ('dwForwardMetric5', wintypes.DWORD)
    ]


class Win32_MIB_IPFORWARDTABLE(ctypes.Structure):
    _fields_ = [
        ('dwNumEntries', wintypes.DWORD),
        ('table', Win32_MIB_IPFORWARDROW * 1)
    ]


GetAdaptersAddresses = windll.Iphlpapi.GetAdaptersAddresses
GetAdaptersAddresses.argtypes = [
    wintypes.ULONG, wintypes.ULONG, wintypes.LPVOID,
    ctypes.POINTER(IP_ADAPTER_ADDRESSES),
    ctypes.POINTER(wintypes.ULONG)]
GetAdaptersAddresses.restype = wintypes.ULONG

GetIpForwardTable = windll.Iphlpapi.GetIpForwardTable
GetIpForwardTable.argtypes = [
    ctypes.POINTER(Win32_MIB_IPFORWARDTABLE),
    ctypes.POINTER(wintypes.ULONG),
    wintypes.BOOL]
GetIpForwardTable.restype = wintypes.DWORD

GetProcessHeap = windll.kernel32.GetProcessHeap
GetProcessHeap.argtypes = []
GetProcessHeap.restype = wintypes.HANDLE

HeapAlloc = windll.kernel32.HeapAlloc
HeapAlloc.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_uint64]
HeapAlloc.restype = wintypes.LPVOID

HeapFree = windll.kernel32.HeapFree
HeapFree.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID]
HeapFree.restype = wintypes.BOOL
ERROR_NO_DATA = 232
GAA_FLAG_INCLUDE_PREFIX = 0x0010
Ws2_32 = windll.Ws2_32
Ws2_32.inet_ntoa.restype = ctypes.c_char_p


def _heap_alloc(heap, size):
    table_mem = HeapAlloc(heap, 0, ctypes.c_size_t(size.value))
    if not table_mem:
        raise MemoryError('Unable to allocate memory for the IP forward table')
    return table_mem


@contextmanager
def _get_forward_table():
    heap = GetProcessHeap()
    size = wintypes.ULONG(0)
    p_forward_table = table_mem = None
    max_tries = 10

    try:
        while max_tries > 0:
            max_tries -= 1
            err = GetIpForwardTable(p_forward_table, ctypes.byref(size), 0)
            if err == ERROR_INSUFFICIENT_BUFFER:
                if p_forward_table is not None:
                    HeapFree(heap, 0, p_forward_table)
                    p_forward_table = None
                table_mem = _heap_alloc(heap, size)
                p_forward_table = ctypes.cast(table_mem, ctypes.POINTER(Win32_MIB_IPFORWARDTABLE))
            elif err in (ERROR_SUCCESS, ERROR_NO_DATA):
                yield p_forward_table
                break
            else:
                raise OSError('Unable to get IP forward table. Error: %s' % err)
        if p_forward_table is None:
            raise OSError('Failed to get IP routing table, table appears to be changing rapidly')
    finally:
        if p_forward_table is not None:
            HeapFree(heap, 0, p_forward_table)


@contextmanager
def _get_adapters():
    heap = GetProcessHeap()
    size = wintypes.ULONG(0)
    addresses = buf = None
    max_tries = 10
    try:
        while max_tries > 0:
            max_tries -= 1
            err = GetAdaptersAddresses(0, GAA_FLAG_INCLUDE_PREFIX, None, addresses, ctypes.byref(size))
            if err in (ERROR_SUCCESS, ERROR_NO_DATA):
                yield addresses
                break
            elif err == ERROR_BUFFER_OVERFLOW:
                if addresses is not None:
                    HeapFree(heap, 0, addresses)
                    addresses = None
                buf = _heap_alloc(heap, size)
                addresses = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
            else:
                raise OSError('Failed to determine size for adapters table with error: %s' % err)
        if addresses is None:
            raise OSError('Failed to get adapter addresses, table appears to be changing rapidly')
    finally:
        if addresses is not None:
            HeapFree(heap, 0, addresses)
            addresses = None


Adapter = namedtuple('Adapter', 'name if_index if_index6 friendly_name status transmit_speed receive_speed')


def adapters():
    ''' A list of adapters on this machine '''
    ans = []
    smap = {1:'up', 2:'down', 3:'testing', 4:'unknown', 5:'dormant', 6:'not-present', 7:'lower-layer-down'}
    with _get_adapters() as p_adapters_list:
        adapter = p_adapters_list
        while adapter:
            adapter = adapter.contents
            if not adapter:
                break
            ans.append(Adapter(
                name=adapter.AdapterName.decode(),
                if_index=adapter.Union1.Struct1.IfIndex,
                if_index6=adapter.Ipv6IfIndex,
                friendly_name=adapter.FriendlyName,
                status=smap.get(adapter.OperStatus, 'unknown'),
                transmit_speed=adapter.TransmitLinkSpeed,
                receive_speed=adapter.ReceiveLinkSpeed
            ))
            adapter = ctypes.cast(adapter.Next, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
    return ans


Route = namedtuple('Route', 'destination gateway netmask interface metric flags')


def routes():
    ''' A list of routes on this machine '''
    ans = []
    adapter_map = {a.if_index:a.name for a in adapters()}
    with _get_forward_table() as p_forward_table:
        if p_forward_table is None:
            return ans
        forward_table = p_forward_table.contents
        table = ctypes.cast(
            ctypes.addressof(forward_table.table),
            ctypes.POINTER(Win32_MIB_IPFORWARDROW * forward_table.dwNumEntries)
        ).contents

        for row in table:
            destination = Ws2_32.inet_ntoa(row.dwForwardDest).decode()
            netmask = Ws2_32.inet_ntoa(row.dwForwardMask).decode()
            gateway = Ws2_32.inet_ntoa(row.dwForwardNextHop).decode()
            ans.append(Route(
                destination=destination,
                gateway=gateway,
                netmask=netmask,
                interface=adapter_map.get(row.dwForwardIfIndex),
                metric=row.dwForwardMetric1,
                flags=row.dwForwardProto
            ))

    return ans


if __name__ == '__main__':
    from pprint import pprint
    pprint(adapters())
    pprint(routes())
