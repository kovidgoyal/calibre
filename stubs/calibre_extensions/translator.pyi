class Translator:
    "Translator"
    def __init__(self, mo_data: bytes | None = None) -> None:
        "Translator"
        pass

    def plural(self, n: int) -> int:
        "plural(n: int) -> int:\n\nGet the message catalog index based on the plural form specification."
        pass

    def add_fallback(self, other: Translator) -> None:
        "add_fallback(other: Translator) -> None:\n\nAdd a fallback translator."
        pass

    def install(self, names: tuple[str, ...] | list[str] | None = None) -> None:
        "install(names=None) -> None:\n\ninstall translation functions into global namespace"
        pass

    def info(self) -> dict[str, str]:
        "info() -> dict[str, str]:\n\nReturn information about the mo file as a dict"
        pass

    def charset(self) -> str | None:
        "charset() -> str:\n\nReturn the character set for this catalog"
        pass

    def gettext(self, message: str) -> str:
        "gettext(message: str) -> str:\n\nTranslate the provided message"
        pass

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        "gettext(singular: str, plural: str, n: int) -> str:\n\nTranslate the provided message"
        pass

    def pgettext(self, context: str, message: str) -> str:
        "pgettext(context: str, message: str) -> str:\n\nTranslate the provided message"
        pass

    def npgettext(self, context: str, singular: str, plural: str, n: int) -> str:
        "gettext(context: str, singular: str, plural: str, n: int) -> str:\n\nTranslate the provided message"
        pass

    def set_as_qt_translator(self) -> int:
        "set_as_qt_translator() -> int:\n\nSet this translator to use as the translator for Qt and return a pointer to the qt_translate() function."
        pass
