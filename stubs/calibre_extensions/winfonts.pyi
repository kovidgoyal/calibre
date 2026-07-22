from typing import Any

def enum_font_families() -> list[dict[str, Any]]:
    """Enumerate all regular (not italic/bold/etc. variants) font families on the system.

    Note there will be multiple entries for every family (corresponding to each charset
    of the font).
    """
    pass

def font_data(family_name: str, italic: bool, weight: int) -> bytes:
    "Return the raw font data for the specified font."
    pass

def add_font(data: bytes) -> int:
    "Add the font(s) in the data (bytestring) to windows. Added fonts are always private. Returns the number of fonts added."
    pass

def add_system_font(path: str) -> int:
    "Add the font(s) in the specified file to the system font tables."
    pass

def remove_system_font(path: str) -> bool:
    "Remove the font(s) in the specified file from the system font tables."
    pass

FW_DONTCARE: int
FW_THIN: int
FW_EXTRALIGHT: int
FW_ULTRALIGHT: int
FW_LIGHT: int
FW_NORMAL: int
FW_REGULAR: int
FW_MEDIUM: int
FW_SEMIBOLD: int
FW_DEMIBOLD: int
FW_BOLD: int
FW_EXTRABOLD: int
FW_ULTRABOLD: int
FW_HEAVY: int
FW_BLACK: int
