from collections.abc import Callable

def parse_css_number(src: str) -> int | float:
    'Parse a CSS number from a string'
    pass

def transform_properties(src: str, url_callback: Callable[[str], str] | None = None, is_declaration: bool = False) -> str:
    'Transform a CSS stylesheet or declaration'
    pass
