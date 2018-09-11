#!/usr/bin/env  python2
from __future__ import print_function
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Create a file handle to a remote file over the sftp protocol.
'''

import sys, socket, getpass
from urlparse import urlparse
from binascii import hexlify

import paramiko


def agent_auth(transport, username):
    """
    Attempt to authenticate to the given transport using any of the private
    keys available from an SSH agent.
    """

    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    if len(agent_keys) == 0:
        return

    for key in agent_keys:
        print('Trying ssh-agent key %s' % hexlify(key.get_fingerprint()), end=' ')
        try:
            transport.auth_publickey(username, key)
            print('... success!')
            return True
        except paramiko.SSHException:
            print('... failed.')
    return False


def portable_getpass(username, hostname, retry):
    return getpass.getpass('%sPlease enter the password for %s on %s: '%(
                                'Incorrect password. ' if retry else '', username, hostname))


def password_auth(transport, username, hostname, getpw=portable_getpass):
    for i in range(3):
        pw = getpw(username, hostname, i>0)
        transport.auth_password(username, pw)
        if transport.is_authenticated():
            return True
    return False


def connect_to_url(url, getpw=portable_getpass, mode='r+', bufsize=-1):
    protocol, host, path = urlparse(url)[:3]
    if protocol != 'sftp':
        raise ValueError(_('URL must have the scheme sftp'))
    try:
        username, host = host.split('@')
    except:
        raise ValueError(_('host must be of the form user@hostname'))
    port = 22
    if ':' in host:
        host, port = host.split(':')
        port = int(port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    t = paramiko.Transport(sock)
    try:
        t.start_client()
    except:
        raise Exception(_('Failed to negotiate SSH session: ') + str(t.get_exception()))
    if not agent_auth(t, username):
        if not password_auth(t, username, host, getpw):
            raise ValueError(_('Failed to authenticate with server: %s')%url)
    sftp = paramiko.SFTPClient.from_transport(t)
    return sftp, sftp.open(path, mode=mode, bufsize=bufsize)


def main(args=sys.argv):
    f = connect_to_url(args[1])[-1]
    print(f.read())
    f.seek(0, 2)
    print(f.tell())
    f.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
