# License: GPLv3 Copyright: 2026

"""Experimental vector diagram preservation, before PDF text reflow."""

import os


def diagram_regions(page, label_gap=12, min_size=12):
    import pymupdf as pdf

    lines = [pdf.Rect(line['bbox'])
             for block in page.get_text('dict')['blocks']
             for line in block.get('lines', [])]
    regions = []
    # size filtering admits tables/logos and misses tiny diagrams;
    # use document-specific filtering if the experimental heuristic falls short.
    for drawing in page.cluster_drawings():
        if drawing.width < min_size or drawing.height < min_size:
            continue
        region = pdf.Rect(drawing)
        for line in lines:
            if (drawing.y0 <= line.y0 and line.y1 <= drawing.y1
                    and line.x0 <= drawing.x1 + label_gap
                    and line.x1 >= drawing.x0 - label_gap):
                region |= line
        regions.append((region + (-2, -2, 2, 2)) & page.rect)
    return sorted(regions, key=lambda r: (r.y0, r.x0))


def diagram_svg(document, index, region):
    import pymupdf as pdf

    with pdf.open() as cropped:
        target = cropped.new_page(width=region.width, height=region.height)
        target.show_pdf_page(target.rect, document, index, clip=region)
        # A visual crop alone retains the whole page in the SVG. Actually remove
        # outside content, including unused glyphs, before serializing it.
        target.clip_to_rect(target.rect)
        return target.get_svg_image(text_as_path=True).encode('utf-8')


def preserve_diagrams(pdf_path, xml, output_dir, log):
    from lxml import etree

    from calibre.ebooks import ConversionError
    from calibre.utils.xml_parse import safe_xml_fromstring

    try:
        import pymupdf as pdf
    except ImportError as err:
        raise ConversionError('PDF diagram detection requires PyMuPDF.') from err
    if not hasattr(pdf.Page, 'clip_to_rect') or not hasattr(pdf.Page, 'cluster_drawings'):
        raise ConversionError('PDF diagram detection requires a newer PyMuPDF with clip_to_rect() and cluster_drawings().')

    root = safe_xml_fromstring(xml)
    count = 0
    with pdf.open(pdf_path) as document:
        for page_xml in root.findall('page'):
            index = int(page_xml.get('number')) - 1
            page = document[index]
            # skip rotated pages until the Poppler/MuPDF coordinate
            # mapping is tested for them; ordinary PDF conversion still works.
            if page.rotation:
                log.warn(f'Skipping diagram detection on rotated PDF page {index + 1}')
                continue
            sx = float(page_xml.get('width')) / page.rect.width
            sy = float(page_xml.get('height')) / page.rect.height
            ox, oy = float(page_xml.get('left', 0)), float(page_xml.get('top', 0))
            for number, region in enumerate(diagram_regions(page), 1):
                name = f'pdf-diagram-{index + 1:04d}-{number:02d}.svg'
                data = diagram_svg(document, index, region)
                with open(os.path.join(output_dir, name), 'wb') as f:
                    f.write(data)
                bounds = pdf.Rect(ox + region.x0 * sx, oy + region.y0 * sy,
                                  ox + region.x1 * sx, oy + region.y1 * sy)
                for element in list(page_xml):
                    if element.tag not in ('text', 'image'):
                        continue
                    x, y = float(element.get('left')), float(element.get('top'))
                    box = pdf.Rect(x, y, x + float(element.get('width')), y + float(element.get('height')))
                    # Remove only fully enclosed objects: partial overlap must
                    # not delete a whole line of prose alongside a diagram.
                    if bounds.contains(box):
                        page_xml.remove(element)
                labels = ' '.join(page.get_text(clip=region).split())
                etree.SubElement(page_xml, 'image', src=name, type='vector-diagram',
                                 alt=f'Diagram: {labels}' if labels else 'Diagram',
                                 left=str(bounds.x0), top=str(bounds.y0),
                                 width=str(bounds.width), height=str(bounds.height))
                count += 1
    log.info(f'Preserved {count} PDF vector diagrams as SVG')
    return etree.tostring(root, encoding='utf-8')
