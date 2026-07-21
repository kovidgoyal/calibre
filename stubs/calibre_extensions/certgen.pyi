def create_rsa_keypair(size: int) -> object:
    "create_rsa_keypair(size)\n\nCreate a RSA keypair of the specified size"
    pass

def create_rsa_cert_req(
    keypair: object,
    alt_names: tuple[str, ...],
    common_name: str,
    country: str | None,
    state: str | None,
    locality: str | None,
    org: str | None,
    org_unit: str | None,
    email_address: str | None,
    basic_constraints: str | None,
    digital_key_usage: str | None,
    ext_key_usage: str | None,
) -> object:
    "create_rsa_cert_req(keypair, alt_names, common_name, country, state, locality, org, org_unit, email_address)\n\nCreate a certificate signing request."
    pass

def create_rsa_cert(req: object, CA_cert: object | None, CA_key: object, not_before: int = 0, expire: int = 1) -> object:
    "create_rsa_cert(req, CA_cert, CA_key, not_before, expire)\n\nCreate a certificate from a signing request."
    pass

def serialize_cert(cert: object) -> bytes:
    "serialize_cert(cert)\n\nReturn certificate as a PEM format bytestring"
    pass

def serialize_rsa_key(key: object, password: str | None) -> bytes:
    "serialize_rsa_key(key, [password])\n\nReturn key as a PEM format bytestring, optionally encrypted by password"
    pass

def cert_info(cert: object) -> bytes:
    "cert_info(cert)\n\nReturn the certificate information (certificate in text format)"
    pass

def verify_cert(cacert: object, cert: object) -> None:
    "verify_cert(cacert, cert)\n\nVerify cert against CA cert"
    pass

def create_CA_dir(cacerts_as_pem_bundle_string: str | bytes, output_path: str) -> None:
    "create_CA_dir(cacerts_as_pem_bundle_string, output_path)\n\nCreate an OpenSSL CA certificate lookup directory. output_path must be an empty directory."
    pass
