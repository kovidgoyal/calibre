def register_jxl_image_format() -> bool:
    "Return True iff the JPEG-XL image format was successfully registered with Qt for reading and writing when this module was imported"
    pass

def is_jxl(data: bytes) -> bool:
    "Return True iff data starts with the header of a JPEG-XL image, either a bare codestream or a container"
    pass
