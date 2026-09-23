# Built-in library placement path

`library_path` is an optional built-in text field, displayed as **Путь размещения**
in Russian. It is available in every library, including libraries created before
this patch. No custom column needs to be created.

An empty value preserves the standard `Author/Title (ID)` directory layout.
`electronics/books` produces `electronics/books/Author/Title (ID)` inside the
current library root. Changing or clearing the field moves the book directory,
including its formats, cover and extra data files. Author/title normalization
and the book ID suffix are unchanged.

## Editing

The field appears on the basic metadata page in all three single-book layouts
and as an editable library-list column. Bulk editing has a path input and an
Apply checkbox: unchecked leaves existing values unchanged; checked applies
the supplied value, including an empty value to clear the prefix. Searches
`library_path:` and the legacy `#library_path:` search alias work. Templates
use `{library_path}`. Category rename/removal also updates physical paths.

## Database and OPF compatibility

The database creates the field's dedicated tables on first open, without
changing book paths or occupying an upstream database schema-version number.
Old libraries without the field continue to work with empty values.

Only nonempty values are written to the book's metadata backup:

```xml
<meta name="calibre:library_path" content="electronics/books"/>
```

Clearing the field removes this entry the next time metadata.opf is backed up.
There is no custom-column description for this field in newly written backups.
The backup is asynchronous, as with other calibre metadata changes.

The earlier single-valued text custom column `#library_path` is migrated
transactionally on opening a library. Values are copied, the old column is
removed, library preferences referencing its lookup name are updated, and OPF
backups are marked for rewriting. Migration itself never moves book folders.
Old OPF backups using the custom field can still be imported/restored. Do not
delete that column manually before migration, because it contains the values
to be transferred. Unrelated custom columns are unchanged.

## Validation and limits

Paths must be relative to the library root. Absolute paths, parent traversal,
empty components, Windows reserved names, unsupported filename characters,
leading-dot components and book-like ` (number)` suffixes are rejected.
Backslashes normalize to slashes. Unicode directory names are retained.
Existing links outside the root and excessively long Windows paths are rejected.

Filesystem moves use calibre's existing implementation and do not provide
rollback across a batch if an I/O error occurs during a move.

## Targeted tests

The ten folder tests cover old-library behavior, compact/omitted OPF, migration
from the older custom column, OPF import, path changes, invalid paths, trash
and database restoration. They create disposable libraries.

```powershell
$env:CALIBRE_DEVELOP_FROM = Join-Path (Get-Location) 'src'
calibre-debug -c "import unittest; from calibre.db.tests.folder import FolderTest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FolderTest)); raise SystemExit(not r.wasSuccessful())"
```
