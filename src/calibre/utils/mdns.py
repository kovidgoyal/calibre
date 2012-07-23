from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import socket, time, atexit

_server = None

def _get_external_ip():
    'Get IP address of interface used to connect to the outside world'
    try:
        ipaddr = socket.gethostbyname(socket.gethostname())
    except:
        ipaddr = '127.0.0.1'
    if ipaddr.startswith('127.'):
        for addr in ('192.0.2.0', '198.51.100.0', 'google.com'):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((addr, 0))
                ipaddr = s.getsockname()[0]
                if not ipaddr.startswith('127.'):
                    break
            except:
                time.sleep(0.3)
    #print 'ipaddr: %s' % ipaddr
    return ipaddr

_ext_ip = None
def get_external_ip():
    global _ext_ip
    if _ext_ip is None:
        _ext_ip = _get_external_ip()
    return _ext_ip

def start_server():
    global _server
    if _server is None:
        from calibre.utils.Zeroconf import Zeroconf
        try:
            _server = Zeroconf()
        except:
            time.sleep(0.2)
            _server = Zeroconf()

        atexit.register(stop_server)

    return _server

def create_service(desc, type, port, properties, add_hostname):
    port = int(port)
    try:
        hostname = socket.gethostname().partition('.')[0]
    except:
        hostname = 'Unknown'

    if add_hostname:
        desc += ' (on %s)'%hostname
    local_ip = get_external_ip()
    type = type+'.local.'
    from calibre.utils.Zeroconf import ServiceInfo
    return ServiceInfo(type, desc+'.'+type,
                          address=socket.inet_aton(local_ip),
                          port=port,
                          properties=properties,
                          server=hostname+'.local.')


def publish(desc, type, port, properties=None, add_hostname=True):
    '''
    Publish a service.

    :param desc: Description of service
    :param type: Name and type of service. For example _stanza._tcp
    :param port: Port the service listens on
    :param properties: An optional dictionary whose keys and values will be put
                       into the TXT record.
    '''
    server = start_server()
    service = create_service(desc, type, port, properties, add_hostname)
    server.registerService(service)

def unpublish(desc, type, port, properties=None, add_hostname=True):
    '''
    Unpublish a service.

    The parameters must be the same as used in the corresponding call to publish
    '''
    server = start_server()
    service = create_service(desc, type, port, properties, add_hostname)
    server.unregisterService(service)
    if server.countRegisteredServices() == 0:
        stop_server()

def stop_server():
    global _server
    if _server is not None:
        try:
            _server.close()
        finally:
            _server = None
