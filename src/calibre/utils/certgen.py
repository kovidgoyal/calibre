#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import socket
from collections.abc import Callable, Sequence
from typing import IO

from calibre_extensions import certgen


def create_key_pair(size: int = 2048) -> object:
    return certgen.create_rsa_keypair(size)


def create_cert_request(
    key_pair: object,
    common_name: str,
    country: str | None = 'IN',
    state: str | None = 'Maharashtra',
    locality: str | None = 'Mumbai',
    organization: str | None = None,
    organizational_unit: str | None = None,
    email_address: str | None = None,
    alt_names: Sequence[str] = (),
    basic_constraints: str | None = None,
    digital_key_usage: str | None = None,
    ext_key_usage: str | None = None,
) -> object:
    return certgen.create_rsa_cert_req(
        key_pair,
        tuple(alt_names),
        common_name,
        country,
        state,
        locality,
        organization,
        organizational_unit,
        email_address,
        basic_constraints,
        digital_key_usage,
        ext_key_usage,
    )


def create_cert(req: object, ca_cert: object, ca_keypair: object, expire: int = 365, not_before: int = 0) -> object:
    return certgen.create_rsa_cert(req, ca_cert, ca_keypair, not_before, expire)


def create_ca_cert(req: object, ca_keypair: object, expire: int = 365, not_before: int = 0) -> object:
    return certgen.create_rsa_cert(req, None, ca_keypair, not_before, expire)


def serialize_cert(cert: object) -> bytes:
    return certgen.serialize_cert(cert)


def serialize_key(key_pair: object, password: str | None = None) -> bytes:
    return certgen.serialize_rsa_key(key_pair, password)


def cert_info(cert: object) -> bytes:
    return certgen.cert_info(cert)


def create_server_cert(
    domain_or_ip: str,
    ca_cert_file: str | IO[bytes] | None = None,
    server_cert_file: str | IO[bytes] | None = None,
    server_key_file: str | IO[bytes] | None = None,
    expire: int = 365,
    ca_key_file: str | IO[bytes] | None = None,
    ca_name: str = 'Dummy Certificate Authority',
    key_size: int = 2048,
    country: str | None = 'IN',
    state: str | None = 'Maharashtra',
    locality: str | None = 'Mumbai',
    organization: str | None = None,
    organizational_unit: str | None = None,
    email_address: str | None = None,
    alt_names: Sequence[str] = (),
    encrypt_key_with_password: str | None = None,
) -> tuple[object, object, object, object]:
    is_ip = False
    try:
        socket.inet_pton(socket.AF_INET, domain_or_ip)
        is_ip = True
    except Exception:
        try:
            socket.inet_pton(socket.AF_INET6, domain_or_ip)
            is_ip = True
        except Exception:
            pass
    if not alt_names:
        prefix = 'IP' if is_ip else 'DNS'
        alt_names = (f'{prefix}:{domain_or_ip}',)

    # Create the Certificate Authority
    cakey = create_key_pair(key_size)
    careq = create_cert_request(
        cakey,
        ca_name,
        basic_constraints='critical,CA:TRUE',
        digital_key_usage='critical,keyCertSign,cRLSign',
        ext_key_usage='critical,serverAuth,clientAuth',
    )
    cacert = create_ca_cert(careq, cakey)

    # Create the server certificate issued by the newly created CA
    pkey = create_key_pair(key_size)
    req = create_cert_request(
        pkey,
        domain_or_ip,
        country,
        state,
        locality,
        organization,
        organizational_unit,
        email_address,
        alt_names,
        digital_key_usage='critical,keyEncipherment,digitalSignature',
        ext_key_usage='critical,serverAuth,clientAuth',
    )
    cert = create_cert(req, cacert, cakey, expire=expire)

    def export(dest: str | IO[bytes] | None, obj: object, func: Callable[..., bytes | str], *args: str | None) -> None:
        if dest is not None:
            data = func(obj, *args)
            if isinstance(data, str):
                data = data.encode('utf-8')
            if hasattr(dest, 'write'):
                dest.write(data)  # ty: ignore[call-non-callable]
            else:
                with open(dest, 'wb') as f:
                    f.write(data)

    export(ca_cert_file, cacert, serialize_cert)
    export(server_cert_file, cert, serialize_cert)
    export(server_key_file, pkey, serialize_key, encrypt_key_with_password)
    export(ca_key_file, cakey, serialize_key, encrypt_key_with_password)
    return cacert, cakey, cert, pkey


def develop() -> None:
    cacert, cakey, cert, pkey = create_server_cert('test.me', alt_names=['DNS:moose.cat', 'DNS:huge.bat'])
    print('CA Certificate')
    print(cert_info(cacert))
    print(), print(), print()
    print('Server Certificate')
    print(cert_info(cert))
    certgen.verify_cert(cacert, cacert)
    certgen.verify_cert(cacert, cert)


if __name__ == '__main__':
    develop()
