from collections.abc import Callable
from typing import Any

def get_appearance(effective: bool = False) -> str:
    'Get the current (or effective) NSApplication appearance name, or the empty string if unset'
    pass

def set_appearance(value: str) -> None:
    'Set the application appearance to one of "system", "light" or "dark"'
    pass

def set_requires_aqua_system_appearance(yes: bool | None) -> None:
    'Set (or if None, remove) the NSRequiresAquaSystemAppearance user default'
    pass

def get_requires_aqua_system_appearance() -> bool | None:
    'Get the NSRequiresAquaSystemAppearance user default, or None if it is unset'
    pass

def transient_scroller() -> bool:
    'Return True if the preferred NSScroller style is the overlay style'
    pass

def cursor_blink_time() -> float:
    'Return the text insertion point blink period in milliseconds, or -1 if the cursor should not blink'
    pass

def enable_cocoa_multithreading() -> None:
    'Start an NSThread so that Cocoa knows the process is multithreaded'
    pass

def set_notification_activated_callback(callback: Callable[[str | None], Any]) -> None:
    'Set the function called with the notification identifier when a user notification is activated'
    pass

def send_notification(identifier: str | None, title: str, informative_text: str | None, use_sound: bool = False, subtitle: str | None = None) -> None:
    'Schedule display of a user notification via UNUserNotificationCenter'
    pass

def disable_cocoa_ui_elements(tabbing: bool = True, menu_items: bool = True) -> None:
    'Disable automatic window tabbing and/or the Start Dictation/Emoji & Symbols/Enter Full Screen menu items'
    pass

def send2trash(path: str) -> None:
    'Move the file at path to the trash'
    pass

def locale_names(*args: str) -> tuple[str, ...]:
    'Return the display name for each of the given language/locale codes in the current locale, falling back to the code itself if unavailable'
    pass

def create_io_pm_assertion(type: str, reason: str, on: bool = True) -> int:
    'Create an IOPMAssertion of the specified type with the specified reason, returning its id'
    pass

def release_io_pm_assertion(assertion_id: int) -> None:
    'Release a previously created IOPMAssertion given its id'
    pass

kIOPMAssertionTypePreventUserIdleSystemSleep: str
kIOPMAssertionTypePreventUserIdleDisplaySleep: str
kIOPMAssertionTypePreventSystemSleep: str
kIOPMAssertionTypeNoIdleSleep: str
kIOPMAssertionTypeNoDisplaySleep: str
