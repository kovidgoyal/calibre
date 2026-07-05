from datetime import datetime
from typing import Any

def deepcopy(object: Any) -> Any:
    'Fast implementation of deepcopy()'
    pass

def parse_date(text: str) -> tuple[int, int, int, int, int, int, int] | None:
    'Parse ISO dates faster (specialized for dates stored in the calibre db).'
    pass

def parse_iso8601(text: str) -> tuple[datetime, bool, int]:
    'Parse ISO 8601 dates faster. More spec compliant than parse_date()'
    pass

def pdf_float(val: float) -> str:
    'Convert float to a string representation suitable for PDF'
    pass

def detach(path: str) -> None:
    'Redirect the standard I/O stream to the specified file (usually os.devnull)'
    pass

def create_texture(width: int, height: int, red: int, green: int, blue: int, blend_red: int = 0, blend_green: int = 0, blend_blue: int = 0, blend_alpha: float = 0.1, density: float = 0.7, weight: int = 3, radius: float = 1) -> bytes:
    'Create a texture of the specified width and height from the specified color. The texture is created by blending in random noise of the specified blend color into a flat image. All colors are numbers between 0 and 255. 0 <= blend_alpha <= 1 with 0 being fully transparent. 0 <= density <= 1 is used to control the amount of noise in the texture. weight and radius control the Gaussian convolution used for blurring of the noise. weight must be an odd positive integer. Increasing the weight will tend to blur out the noise. Decreasing it will make it sharper. This function returns an image (bytestring) in the PPM format as the texture.'
    pass

def websocket_mask(data: bytearray | memoryview, mask: bytes | memoryview, offset: int = 0) -> None:
    'XOR the data (bytestring) with the specified (must be 4-byte bytestring) mask'
    pass

def utf8_decode(data: bytes, state: int = 0, codep: int = 0) -> tuple[str, int, int]:
    'Decode an UTF-8 bytestring, using a strict UTF-8 decoder, that unlike python does not allow orphaned surrogates. Returns a unicode object and the state.'
    pass

def clean_xml_chars(unicode_object: str) -> str:
    'Remove codepoints in unicode_object that are not allowed in XML'
    pass

def set_thread_name(name: str) -> None:
    'Wrapper for pthread_setname_np'
    pass

def pread_all(fd: int, n: int, offset: int = 0) -> bytes:
    'Read upto n bytes from the specified fd at offset in a thread safe manner. If less than n bytes are returned it means there were less than n bytes in the file at offset. Only works with seekable regular files, not sockets/ttys/etc. Note that on Windows it moves the file pointer so cannot be mixed with calls to tell() or ordinary reads.'
    pass

def get_num_of_significant_chars(elem: Any) -> int:
    'Get the number of chars in specified tag'
    pass

def barename(tag: str) -> str:
    'Get bare tag name without namespace'
    pass

def namespace(tag: str) -> str:
    'Get namespace of the tag'
    pass

O_CLOEXEC: int
