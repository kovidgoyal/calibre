class Error(Exception):
    pass

cache: dict[tuple[int, int, int, int, int], dict[str, str]]

def get_devices() -> list[tuple[tuple[int, int, int, int, int], dict[str, str]]]:
    'get_devices()\n\nGet the list of USB devices on the system.'
    pass
