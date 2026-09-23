# PDF ↔ DjVu with existing text, without OCR

The DJVU output plugin exposes DJVU in calibre's conversion dialog. PDF to
DJVU and DJVU/DJV to PDF take a direct page-preserving route, bypassing the
HTML/reflow pipeline. DJVU output currently accepts only PDF input.

PDF → DJVU uses Poppler pdftoppm and pdftotext, then DjVuLibre c44, djvused
and djvm. Word bounding boxes from the PDF become DjVu text zones.

DJVU → PDF uses ddjvu and djvused, then Qt's PDF writer. Existing text zones
are written in the PDF underneath the opaque page image, so the visible scan
is unchanged and the text remains searchable/extractable/selectable.

Both directions rasterize at 300 DPI, retain page order and physical page
sizes, and transfer available text. There is no OCR and no network service.
Pages without text stay without text. Existing OCR errors are retained.

This is a raster conversion: vector content is not retained as vectors.
Bookmarks, interactive links, annotations, forms and signatures are not
transferred. Reflow, font, cover insertion, and page-layout conversion
settings do not apply to this direct route. Output files may be larger than
their inputs. Self-contained DjVu files are supported; indirect documents
depending on external page files are not supported by the temporary-copy path.

Tests run through Plumber in both directions on a three-page document with
Cyrillic/Latin text, portrait and landscape pages and a text-free drawing.
They verify page counts, extracted text, absent text on the scan-only page,
and rendered dimensions. The DJVU output selection was visually checked in
the real conversion configuration dialog using a disposable library.

Run with calibre-debug and CALIBRE_DEVELOP_FROM set to this checkout's src:

```python
import unittest
from calibre.ebooks.djvu.convert_test import ConversionTest
unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ConversionTest))
```
