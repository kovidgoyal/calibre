from typing import ClassVar

from qt.core import QFont, QImage, QKeyEvent, QMouseEvent, QObject, QPaintEvent, QResizeEvent, QSize, QTimerEvent, QWidget, pyqtSignal

class FlowImages(QObject):
    'Base class implemented in Python to supply images, captions and subtitles to a PictureFlow widget'

    dataChanged: ClassVar[pyqtSignal]

    def count(self) -> int:
        'Return the number of images'
        pass

    def image(self, index: int) -> QImage:
        'Return the image at index'
        pass

    def caption(self, index: int) -> str:
        'Return the caption for the image at index'
        pass

    def subtitle(self, index: int) -> str:
        'Return the subtitle for the image at index'
        pass

class PictureFlow(QWidget):
    'A widget that displays a coverflow-like animated list of images'

    itemActivated: ClassVar[pyqtSignal]
    currentChanged: ClassVar[pyqtSignal]
    stop: ClassVar[pyqtSignal]

    def __init__(self, parent: QWidget | None = None, queueLength: int = 3) -> None:
        'Create a new PictureFlow widget, optionally caching queueLength slides on either side of the current slide'
        pass

    def setImages(self, images: FlowImages) -> None:
        'Set the FlowImages instance used to supply images, captions and subtitles'
        pass

    def count(self) -> int:
        'Return the number of images'
        pass

    def slideSize(self) -> QSize:
        'Return the size at which slides are rendered'
        pass

    def setSlideSize(self, size: QSize) -> None:
        'Set the size at which slides are rendered'
        pass

    def activateOnDoubleClick(self) -> bool:
        'Return whether double clicking a slide activates it, instead of a single click'
        pass

    def setActivateOnDoubleClick(self, on: bool) -> None:
        'Set whether double clicking a slide activates it, instead of a single click'
        pass

    def preserveAspectRatio(self) -> bool:
        'Return whether the aspect ratio of images is preserved when scaling'
        pass

    def setPreserveAspectRatio(self, preserve: bool) -> None:
        'Set whether the aspect ratio of images is preserved when scaling'
        pass

    def subtitleFont(self) -> QFont:
        'Return the font used to render subtitles'
        pass

    def setSubtitleFont(self, font: QFont) -> None:
        'Set the font used to render subtitles'
        pass

    def clearCaches(self) -> None:
        'Clear all cached, rendered slide images'
        pass

    def slide(self, index: int) -> QImage:
        'Return the rendered slide image for index'
        pass

    def currentSlide(self) -> int:
        'Return the index of the currently centered slide'
        pass

    def showReflections(self) -> bool:
        'Return whether reflections are drawn below slides'
        pass

    def setShowReflections(self, show: bool) -> None:
        'Set whether reflections are drawn below slides'
        pass

    def maxFontSize(self) -> int:
        'Return the maximum font size used for captions and subtitles'
        pass

    def setMaxFontSize(self, val: int) -> None:
        'Set the maximum font size used for captions and subtitles'
        pass

    def setCurrentSlide(self, index: int) -> None:
        'Make index the currently centered slide, without animation'
        pass

    def render(self, *args, **kwargs) -> None:
        'Re-render the widget'
        pass

    def showPrevious(self) -> None:
        'Animate to the previous slide'
        pass

    def showNext(self) -> None:
        'Animate to the next slide'
        pass

    def showSlide(self, index: int) -> None:
        'Animate to the slide at index'
        pass

    def dataChanged(self) -> None:
        'Call this slot when the underlying FlowImages data has changed'
        pass

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        pass

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        pass

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        pass

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        pass

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        pass

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        pass

    def timerEvent(self, a0: QTimerEvent | None) -> None:
        pass
