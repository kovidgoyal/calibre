from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import socket

_server = None

def get_external_ip():
    'Get IP address of interface used to connect to the outside world'
    try:
        ipaddr = socket.gethostbyname(socket.gethostname())
    except:
        ipaddr = '127.0.0.1'
    if ipaddr == '127.0.0.1':
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('google.com', 0))
            ipaddr = s.getsockname()[0]
        except:
            pass
    return ipaddr

def start_server():
    global _server
    if _server is None:
        from calibre.utils.Zeroconf import Zeroconf
        _server = Zeroconf()
    return _server

def publish(desc, type, port, properties=None, add_hostname=True):
    '''
    Publish a service.
    
    :param desc: Description of service
    :param type: Name and type of service. For example _stanza._tcp
    :param port: Port the service listens on
    :param properties: An optional dictionary whose keys and values will be put 
                       into the TXT record. 
    '''
    port = int(port)
    server = start_server()
    hostname = socket.gethostname()
    if add_hostname:
        desc += ' (on %s)'%hostname
    local_ip = get_external_ip()
    type = type+'.local.'
    from calibre.utils.Zeroconf import ServiceInfo
    service = ServiceInfo(type, desc+'.'+type,
                          address=socket.inet_aton(local_ip),
                          port=port,
                          properties=properties,
                          server=hostname+'.local.')
    server.registerService(service)
    
def stop_server():
    global _server
    if _server is not None:
        _server.close()

'''
class Publish(object):
    
    def __init__(self, desc, name, port, txt=''):
        self.desc = desc
        self.name = name
        self.port = port
        self.txt  = txt
        
    def start(self):
        if iswindows:
            return
        if isosx:
            args = ['dns-sd', self.desc, self.name, '.', self.port]
        else:
            args = ['avahi-publish-service', self.desc, self.name, self.port]
        if self.txt:
            args.append(self.txt)
            
        self.process = subprocess.Popen(args)
    
    def stop(self):
        if iswindows:
            pass
        else:
            process = getattr(self, 'process', None)
            if process is not None:
                process.poll()
                if process.returncode is not None:
                    process.terminate()
                    process.poll()
                    if process.returncode is not None:
                        process.kill()

def publish(desc, name, port, txt):
''' 