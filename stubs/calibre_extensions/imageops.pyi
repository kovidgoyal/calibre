from collections.abc import Sequence

from qt.core import QColor, QImage

def load_from_data_without_gil(image: QImage, data: bytes) -> bool:
    "Load image data (the raw bytes of an encoded image file) into image, without holding the GIL"
    pass

def remove_borders(image: QImage, fuzz: float) -> QImage:
    "Remove border pixels from image that are within fuzz of the border color"
    pass

def grayscale(image: QImage) -> QImage:
    "Convert image to grayscale"
    pass

def gaussian_sharpen(img: QImage, radius: float, sigma: float, high_quality: bool = True) -> QImage:
    "Sharpen img using a Gaussian convolution kernel of the specified radius and sigma"
    pass

def gaussian_blur(img: QImage, radius: float, sigma: float) -> QImage:
    "Blur img using a Gaussian convolution kernel of the specified radius and sigma"
    pass

def despeckle(image: QImage) -> QImage:
    "Reduce noise in image using a despeckle filter"
    pass

def overlay(image: QImage, canvas: QImage, left: int, top: int) -> None:
    "Overlay image onto canvas at the specified left, top position"
    pass

def normalize(image: QImage) -> QImage:
    "Normalize the contrast of image"
    pass

def oil_paint(image: QImage, radius: float = -1, high_quality: bool = True) -> QImage:
    "Apply an oil painting effect to image using the specified radius"
    pass

def dominant_color(image: QImage) -> QColor:
    "Return the dominant color in image"
    pass

def quantize(image: QImage, maximum_colors: int, dither: bool, palette: Sequence[int]) -> QImage:
    "Quantize image to at most maximum_colors colors, optionally dithering, using the specified palette of QRgb values"
    pass

def has_transparent_pixels(image: QImage) -> bool:
    "Return True if image has any transparent pixels"
    pass

def set_opacity(image: QImage, alpha: float) -> QImage:
    "Return a copy of image with its opacity set to alpha (0.0 - 1.0)"
    pass

def texture_image(image: QImage, texturei: QImage) -> QImage:
    "Tile texturei to cover image and return the result"
    pass

def ordered_dither(image: QImage) -> QImage:
    "Apply ordered dithering to image"
    pass
