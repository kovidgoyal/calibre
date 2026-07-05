def get_usb_devices() -> list[tuple[int, int, int, str | None, str | None, str | None]]:
    'Get list of connected USB devices. Returns a list of tuples. Each tuple is of the form (vendor_id, product_id, bcd, manufacturer, product, serial number).'
    pass

def get_usb_drives() -> list[tuple[str, int, int, int, str | None, str | None, str | None]]:
    'Get list of mounted drives. Returns a list of tuples, each of the form (name, bsd_path).'
    pass

def get_mounted_filesystems() -> dict[str, str]:
    'Get mapping of mounted filesystems. Mapping is from BSD name to mount point.'
    pass

def user_locale() -> str | None:
    "user_locale() -> The name of the current user's locale or None if an error occurred"
    pass

def date_format() -> str | None:
    "date_format() -> The (short) date format used by the user's current locale"
    pass

def is_mtp_device(vendor_id: int, product_id: int, bcd: int, serial: str | bytes) -> bool | None:
    'is_mtp_device(vendor_id, product_id, bcd, serial) -> Return True if the specified device has an MTP interface'
    pass
