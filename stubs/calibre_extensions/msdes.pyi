class MsDesError(Exception):
    pass

EN0: int
DE1: int

def deskey(key: bytes, edf: int) -> None:
    'Provide a new key for DES en/decryption.'
    pass

def des(data: bytes) -> bytes:
    'Perform DES en/decryption.'
    pass
