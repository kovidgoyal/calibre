from typing import Any

class Error(Exception):
    pass

class PDFOutlineItem:
    def __init__(self) -> None:
        'PDF Outline items'
        pass

    def create(self, title: str, pagenum: int, as_child: object = False, left: float = 0, top: float = 0, zoom: float = 0) -> PDFOutlineItem:
        (
            "create(title, pagenum, as_child=False) -> Create a new outline item with title 'title', pointing to page number pagenum. If as_child is True the"
            ' new item will be a child of this item otherwise it will be a sibling. Returns the newly created item.'
        )
        pass

    def erase(self) -> None:
        'erase() -> Delete this item and all its children, removing it from the outline tree completely.'
        pass

class PDFDoc:
    title: str
    author: str
    subject: str
    keywords: str
    creator: str
    producer: str
    pages: int
    version: str

    def __init__(self) -> None:
        'PDF Documents'
        pass

    def load(self, buffer: bytes) -> None:
        'Load a PDF document from a byte buffer (string)'
        pass

    def open(self, path: str) -> None:
        'Load a PDF document from a file path (string)'
        pass

    def save(self, path: str) -> None:
        'Save the PDF document to a path on disk'
        pass

    def write(self) -> bytes:
        'Return the PDF document as a bytestring.'
        pass

    def save_to_fileobj(self, f: Any) -> None:
        'Write the PDF document to the soecified file-like object.'
        pass

    def uncompress(self) -> None:
        'Uncompress the PDF'
        pass

    def extract_first_page(self) -> None:
        'extract_first_page() -> Remove all but the first page.'
        pass

    def page_count(self) -> int:
        'page_count() -> Number of pages in the PDF.'
        pass

    def image_count(self) -> int:
        'image_count() -> Number of images in the PDF.'
        pass

    def extract_anchors(self) -> dict[str, tuple[int, float, float, int]]:
        'extract_anchors() -> Extract information about links in the document.'
        pass

    def alter_links(self, alter_callback: Any, mark_links: bool) -> int:
        'alter_links() -> Change links in the document.'
        pass

    def list_fonts(self, get_font_data: bool = False) -> list[dict[str, Any]]:
        'list_fonts() -> Get list of fonts in document'
        pass

    def remove_unused_fonts(self) -> int:
        'remove_unused_fonts() -> Remove unused font objects.'
        pass

    def merge_fonts(self, data: bytes, references: tuple[tuple[int, int], ...]) -> None:
        'merge_fonts() -> Merge the specified fonts.'
        pass

    def replace_font_data(self, data: bytes, num: int, generation: int) -> None:
        'replace_font_data() -> Replace the data stream for the specified font.'
        pass

    def dedup_type3_fonts(self) -> int:
        'dedup_type3_fonts() -> De-duplicate repeated glyphs in Type3 fonts'
        pass

    def impose(self, dest_page_num: int, src_page_num: int, count: int) -> None:
        'impose() -> impose pages onto each other'
        pass

    def dedup_images(self) -> int:
        'dedup_images() -> Remove duplicated images'
        pass

    def delete_pages(self, page_num: int, count: int = 1) -> None:
        'delete_page(page_num, count=1) -> Delete the specified pages from the pdf.'
        pass

    def get_page_box(self, which: str, page_num: int) -> tuple[float, float, float, float]:
        'get_page_box(which, page_num) -> Get the specified box for the specified page as (left, bottom, width, height) in pts'
        pass

    def set_page_box(self, which: str, page_num: int, left: float, bottom: float, width: float, height: float) -> None:
        'set_page_box(which, page_num, left, bottom, width, height) -> Set the specified box (in pts) for the specified page.'
        pass

    def copy_page(self, from_: int, to: int) -> None:
        'copy_page(from, to) -> Copy the specified page.'
        pass

    def append(self, *docs: PDFDoc) -> None:
        'append(doc) -> Append doc (which must be a PDFDoc) to this document.'
        pass

    def insert_existing_page(self, src_doc: PDFDoc, src_page: int = 0, at: int = 0) -> None:
        'insert_existing_page(src_doc, src_page, at) -> Insert the page src_page from src_doc at index: at.'
        pass

    def set_box(self, page_num: int, box: str, left: float, bottom: float, width: float, height: float) -> None:
        (
            'set_box(page_num, box, left, bottom, width, height) -> Set the PDF bounding box for the page numbered nu, box must be one of: MediaBox, CropBox,'
            ' TrimBox, BleedBox, ArtBox. The numbers are interpreted as pts.'
        )
        pass

    def create_outline(self, title: str, pagenum: int, left: float = 0, top: float = 0, zoom: float = 0) -> PDFOutlineItem:
        'create_outline(title, pagenum) -> Create an outline, return the first outline item.'
        pass

    def get_outline(self) -> dict[str, Any] | None:
        'get_outline() -> Get the outline if any in the PDF file.'
        pass

    def get_xmp_metadata(self) -> bytes | None:
        'get_xmp_metadata(raw) -> Get the XMP metadata as raw bytes'
        pass

    def set_xmp_metadata(self, raw: bytes) -> None:
        'set_xmp_metadata(raw) -> Set the XMP metadata to the raw bytes (which must be a valid XML packet)'
        pass

    def add_image_page(
        self,
        image_data: bytes,
        page_x: float,
        page_y: float,
        page_width: float,
        page_height: float,
        image_x: float,
        image_y: float,
        image_canvas_width: float,
        image_canvas_height: float,
        page_num: int = 1,
        preserve_aspect_ratio: bool = True,
    ) -> tuple[float, float]:
        'add_image_page(image_data, page_idx=0) -> Add the specified image as a full page image, will use the size of the first existing page as page size.'
        pass
