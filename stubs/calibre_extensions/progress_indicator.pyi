from typing import ClassVar

from qt.core import QAction, QColor, QIcon, QImage, QMenu, QObject, QPainter, QPaintEvent, QProxyStyle, QRect, QSize, QWidget, pyqtSignal

def set_no_activate_on_click(widget: QWidget) -> None:
    'Prevent widget from activating (getting focus) when it is clicked'
    pass

def draw_snake_spinner(painter: QPainter, rect: QRect, angle: int, light: QColor, dark: QColor) -> None:
    'Draw a single frame of the snake spinner animation, at angle, inside rect using painter'
    pass

def set_menu_on_action(ac: QAction, menu: QMenu) -> None:
    'Associate menu with the QAction ac, so that it can be retrieved with menu_for_action()'
    pass

def menu_for_action(ac: QAction) -> QMenu | None:
    'Return the QMenu previously associated with ac using set_menu_on_action(), or None'
    pass

def set_image_allocation_limit(megabytes: int) -> None:
    'Set the maximum amount of memory, in MB, Qt is allowed to allocate for a single image'
    pass

def get_image_allocation_limit() -> int:
    'Return the maximum amount of memory, in MB, Qt is allowed to allocate for a single image'
    pass

def image_from_hicon(handle: int) -> QImage:
    'Create a QImage from a Windows HICON native handle'
    pass

def image_from_hbitmap(handle: int) -> QImage:
    'Create a QImage from a Windows HBITMAP native handle'
    pass

def contrast_ratio(c1: QColor, c2: QColor) -> float:
    'Return the WCAG contrast ratio between the two colors'
    pass

def utf16_slice(src: str, pos: int, n: int = -1) -> str:
    'Return the sub-string of src starting at UTF-16 code unit pos and containing n UTF-16 code units (-1 for the rest of the string)'
    pass

def set_icon_theme(is_dark: bool, has_dark_user_theme: bool, has_light_user_theme: bool, has_any_user_theme: bool) -> None:
    'Configure the icon theme engine based on whether the palette is dark and which user icon themes are installed'
    pass

def icon_from_name(name: str, fallback_data: bytes) -> QIcon:
    'Return a QIcon for the named icon from the current icon theme, using fallback_data (image data) if not found'
    pass

def icon_from_paths(any_path: str, light_path: str, dark_path: str) -> QIcon:
    'Return a QIcon that is theme aware, constructed from the given light/dark/any variant image paths'
    pass

def install_qt_translator(v: int | None) -> None:
    'Install v (a native QTranslator pointer) as an application translator, or the default translator if v is None'
    pass

class CalibreStyle(QProxyStyle):
    'A QProxyStyle subclass implementing calibre specific UI style tweaks'

    def __init__(self, transient_scroller: int) -> None:
        'Create the style, transient_scroller controls whether scrollbars are transient'
        pass

class SpinAnimator(QObject):
    'Drives the animation for a spinning "busy" indicator'

    updated: ClassVar[pyqtSignal]

    def __init__(self, parent: QObject | None = None, speed_factor: int = 300) -> None:
        'Create the animator, optionally parented to parent, animating at speed_factor'
        pass

    def get_arc_length(self) -> float:
        'Return the current arc length of the spinner, in degrees'
        pass

    def get_arc_rotation(self) -> int:
        'Return the current rotation of the spinner arc, in degrees'
        pass

    def get_overall_rotation(self) -> int:
        'Return the current overall rotation of the spinner, in degrees'
        pass

    def draw(self, painter: QPainter, bounds: QRect, color: QColor, thickness: float = 0.0) -> None:
        'Draw the current animation frame using painter, inside bounds, in color, with the given line thickness'
        pass

    def start(self) -> None:
        'Start the animation'
        pass

    def stop(self) -> None:
        'Stop the animation'
        pass

    def is_running(self) -> bool:
        'Return True if the animation is currently running'
        pass

    def set_arc_length(self, val: float) -> None:
        'Set the arc length of the spinner, in degrees'
        pass

    def set_arc_rotation(self, val: int) -> None:
        'Set the rotation of the spinner arc, in degrees'
        pass

    def set_overall_rotation(self, val: int) -> None:
        'Set the overall rotation of the spinner, in degrees'
        pass

class QProgressIndicator(QWidget):
    'A widget that displays a spinning busy/progress indicator'

    running_state_changed: ClassVar[pyqtSignal]

    def __init__(self, parent: QWidget | None = None, size: int = 64, interval: int = 0) -> None:
        'Create the indicator, optionally parented to parent, with the given size and animation interval (0 for default)'
        pass

    def isAnimated(self) -> bool:
        'Return True if the animation is currently running'
        pass

    def sizeHint(self) -> QSize:
        'Return the recommended size for the widget'
        pass

    def heightForWidth(self, w: int) -> int:
        'Return the recommended height for the given width'
        pass

    def displaySize(self) -> QSize:
        'Return the size at which the indicator is displayed'
        pass

    def startAnimation(self) -> None:
        'Start the animation'
        pass

    def start(self) -> None:
        'Start the animation'
        pass

    def stopAnimation(self) -> None:
        'Stop the animation'
        pass

    def stop(self) -> None:
        'Stop the animation'
        pass

    def setDisplaySize(self, size: QSize | int) -> None:
        'Set the size at which the indicator is displayed'
        pass

    def setSizeHint(self, size: QSize | int) -> None:
        'Set the recommended size for the widget'
        pass

    def paintEvent(self, event: QPaintEvent) -> None:
        pass
