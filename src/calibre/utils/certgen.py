#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import socket
from polyglot.builtins import unicode_type
from calibre_extensions import certgen


def create_key_pair(size=2048):
    return certgen.create_rsa_keypair(size)


def create_cert_request(
    key_pair, common_name,
    country='IN', state='Maharashtra', locality='Mumbai', organization=None,
    organizational_unit=None, email_address=None, alt_names=(), basic_constraints=None
):
    def enc(x):
        if isinstance(x, unicode_type):
            x = x.encode('ascii')
        return x or None

    return certgen.create_rsa_cert_req(
        key_pair, tuple(enc(x) for x in alt_names if x), common_name,
        country, state, locality, organization, organizational_unit, email_address, basic_constraints
    )


def create_cert(req, ca_cert, ca_keypair, expire=365, not_before=0):
    return certgen.create_rsa_cert(req, ca_cert, ca_keypair, not_before, expire)


def create_ca_cert(req, ca_keypair, expire=365, not_before=0):
    return certgen.create_rsa_cert(req, None, ca_keypair, not_before, expire)


def serialize_cert(cert):
    return certgen.serialize_cert(cert)


def serialize_key(key_pair, password=None):
    return certgen.serialize_rsa_key(key_pair, password)


def cert_info(cert):
    return certgen.cert_info(cert).decode('utf-8')


def create_server_cert(
    domain_or_ip, ca_cert_file=None, server_cert_file=None, server_key_file=None,
    expire=365, ca_key_file=None, ca_name='Dummy Certificate Authority', key_size=2048,
    country='IN', state='Maharashtra', locality='Mumbai', organization=None,
    organizational_unit=None, email_address=None, alt_names=(), encrypt_key_with_password=None,
):
    is_ip = False
    try:
        socket.inet_pton(socket.AF_INET, domain_or_ip)
        is_ip = True
    except Exception:
        try:
            socket.inet_aton(socket.AF_INET6, domain_or_ip)
            is_ip = True
        except Exception:
            pass
    if not alt_names:
        prefix = 'IP' if is_ip else 'DNS'
        alt_names = ('{}:{}'.format(prefix, domain_or_ip),)

    # Create the Certificate Authority
    cakey = create_key_pair(key_size)
    careq = create_cert_request(cakey, ca_name, basic_constraints='CA:TRUE')
    cacert = create_ca_cert(careq, cakey)

    # Create the server certificate issued by the newly created CA
    pkey = create_key_pair(key_size)
    req = create_cert_request(pkey, domain_or_ip, country, state, locality, organization, organizational_unit, email_address, alt_names)
    cert = create_cert(req, cacert, cakey, expire=expire)

    def export(dest, obj, func, *args):
        if dest is not None:
            data = func(obj, *args)
            if isinstance(data, unicode_type):
                data = data.encode('utf-8')
            if hasattr(dest, 'write'):
                dest.write(data)
            else:
                with open(dest, 'wb') as f:
                    f.write(data)
    export(ca_cert_file, cacert, serialize_cert)
    export(server_cert_file, cert, serialize_cert)
    export(server_key_file, pkey, serialize_key, encrypt_key_with_password)
    export(ca_key_file, cakey, serialize_key, encrypt_key_with_password)
    return cacert, cakey, cert, pkey


if __name__ == '__main__':
    cacert, cakey, cert, pkey = create_server_cert('test.me', alt_names=['1.test.me', '*.all.test.me'])
    print("CA Certificate")
    print(cert_info(cacert).encode('utf-8'))
    print(), print(), print()
    print('Server Certificate')
    print(cert_info(cert).encode('utf-8'))
