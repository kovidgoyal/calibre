class LZXError(Exception):
    pass

class Compressor:
    reset: int
    wbits: int
    blocksize: int

    def __init__(self, wbits: int, reset: bool = True) -> None:
        'Compressor objects'
        pass

    def compress(self, data: bytes, flush: bool = False) -> tuple[bytes, list[tuple[int, int]]]:
        'Return a string containing data LZX compressed.'
        pass

    def flush(self) -> tuple[bytes, list[tuple[int, int]]]:
        'Return a string containing any remaining LZX compressed data.'
        pass

def init(window: int) -> None:
    'Initialize the LZX decompressor'
    pass

def reset() -> None:
    'Reset the LZX decompressor'
    pass

def decompress(data: bytes, outlen: int) -> bytes:
    'Run the LZX decompressor'
    pass
