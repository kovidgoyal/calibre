# DjVu cover extraction

Requires a separate DjVuLibre installation with `ddjvu`. On Windows, the
reader searches PATH and the DjVuLibre directories in Program Files and
Program Files (x86). `CALIBRE_DDJVU` can specify the executable explicitly.
Windows installation: `winget install --id DjVuLibre.DjView --exact`.

The metadata reader renders page 1 for normal imports (when reading metadata
from files is enabled). Quick metadata reads do not render. Both the metadata
editor and the book-details cover action offer the existing page chooser for
DJVU and DJV, ten pages at a time. Existing covers are not changed merely by
opening the library. Use the chooser to update existing books.

Rendering uses a temporary copy, a 120-second subprocess timeout, and an image
size bounded by 1200 x 1600. Outputs are JPEG. This implementation is intended
for self-contained/bundled DjVu files; indirect documents with external page
files are not supported by the temporary-copy workflow.

DjVuLibre is GPL-2.0-or-later. No DjVuLibre binaries or source code are copied
into this repository. Distribution of an installer bundling DjVuLibre still
requires its license notices and corresponding-source arrangements.

Validation: four tests passed with DjVuLibre 3.5.29 on Windows, using an actual
Radio 1980-01 journal for cover extraction, pages 1-10 and 11-20, end-of-document
behavior and invalid data. The initial ten thumbnails and More pages were also
checked in the rendered chooser. Set CALIBRE_TEST_DJVU to a journal file to run
the real-file test; it is skipped when no sample is supplied.
