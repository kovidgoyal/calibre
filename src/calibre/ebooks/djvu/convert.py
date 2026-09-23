# License: GPLv3
"""Page-preserving PDF/DjVu conversion with an existing searchable text layer."""
import ast
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from calibre.constants import iswindows
from calibre.ebooks.metadata.djvu import find_ddjvu
from calibre.ebooks.metadata.pdf import get_tools
from calibre.ptempfile import TemporaryDirectory

DPI = 300


def run(tool, args, work):
    result = subprocess.run([tool, *args], cwd=work, capture_output=True,
                            timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if iswindows else 0)
    if result.returncode:
        raise ValueError(os.path.basename(tool) + ': ' + result.stderr.decode('utf-8', 'replace')[-3000:])
    return result.stdout


def djvu_tool(name):
    suffix = '.exe' if iswindows else ''
    path = os.path.join(os.path.dirname(find_ddjvu()), name + suffix)
    if os.path.isfile(path):
        return path
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError('DjVuLibre tool not found: ' + name)
    return path


def descendants(element, name):
    return (x for x in element.iter() if x.tag.rsplit('}', 1)[-1] == name)


def pdf_text(page, width, height):
    sx, sy = width / float(page.attrib['width']), height / float(page.attrib['height'])

    def box(node):
        x0, y0, x1, y1 = (float(node.attrib[x]) for x in ('xMin', 'yMin', 'xMax', 'yMax'))
        return f'{max(0, round(x0 * sx))} {max(0, round(height - y1 * sy))} {min(width, round(x1 * sx))} {min(height, round(height - y0 * sy))}'

    lines = []
    for line in descendants(page, 'line'):
        words = [f'(word {box(word)} {json.dumps("".join(word.itertext()), ensure_ascii=False)})'
                 for word in descendants(line, 'word')]
        if words:
            lines.append(f'(line {box(line)} ' + ' '.join(words) + ')')
    return f'(page 0 0 {width} {height} ' + '\n'.join(lines) + ')', len(lines)


def parse_text(data):
    """Parse djvused's bounded, non-executable s-expression text output."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', data.lstrip('\ufeff'))
    roots, stack = [], []
    for token in tokens:
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError('Invalid DjVu text tree')
            stack.pop()
        else:
            if not stack:
                raise ValueError('Invalid DjVu text token')
            stack[-1].append(ast.literal_eval(token) if token.startswith('"') else token)
    if stack:
        raise ValueError('Incomplete DjVu text tree')
    return roots


def text_zones(node):
    if not isinstance(node, list) or len(node) < 6:
        return
    # Leaf zones can be words, lines, or whole pages depending on the producer.
    children = [x for x in node[5:] if isinstance(x, list)]
    if children:
        for child in children:
            yield from text_zones(child)
    else:
        text = ' '.join(str(x) for x in node[5:])
        if text:
            yield tuple(float(x) for x in node[1:5]), text


def pdf_to_djvu(work, progress, log):
    from qt.core import QImage

    info, render = get_tools()
    text_tool = os.path.join(os.path.dirname(info), 'pdftotext' + ('.exe' if iswindows else ''))
    c44, edit = djvu_tool('c44'), djvu_tool('djvused')
    run(text_tool, ['-bbox-layout', '-cropbox', '-enc', 'UTF-8', 'source.pdf', 'text.html'], work)
    pages = list(descendants(ET.parse(os.path.join(work, 'text.html')).getroot(), 'page'))
    if not pages:
        raise ValueError('No PDF pages found')
    with_text = 0
    for number, page in enumerate(pages, 1):
        progress((number - 1) / len(pages), f'PDF → DJVU: {number}/{len(pages)}')
        run(render, ['-f', str(number), '-l', str(number), '-singlefile', '-cropbox', '-r', str(DPI),
                     'source.pdf', 'raster'], work)
        image = QImage(os.path.join(work, 'raster.ppm'))
        if image.isNull():
            raise ValueError('PDF page rendering failed')
        name = f'page-{number:06d}.djvu'
        run(c44, ['-dpi', str(DPI), 'raster.ppm', name], work)
        text, count = pdf_text(page, image.width(), image.height())
        if count:
            with_text += 1
            with open(os.path.join(work, 'text.txt'), 'w', encoding='utf-8') as out:
                out.write(text)
            run(edit, ['-s', '-e', 'select 1; set-txt text.txt', name], work)
        os.remove(os.path.join(work, 'raster.ppm'))
    # Append pages individually to avoid Windows command-line length limits.
    assembler = djvu_tool('djvm')
    run(assembler, ['-c', 'result.djvu', 'page-000001.djvu'], work)
    for number in range(2, len(pages) + 1):
        run(assembler, ['-i', 'result.djvu', f'page-{number:06d}.djvu'], work)
    log(f'Text transferred on {with_text}/{len(pages)} pages. No OCR performed.')
    return 'result.djvu'


def djvu_to_pdf(work, progress, log):
    from qt.core import QFont, QFontMetricsF, QImage, QMarginsF, QPageLayout, QPageSize, QPainter, QPdfWriter, QPointF, QRectF, QSizeF

    from calibre.gui2 import must_use_qt

    must_use_qt()
    edit, render = djvu_tool('djvused'), find_ddjvu()
    count = int(run(edit, ['-e', 'n', 'source.djvu'], work).strip())
    if count < 1:
        raise ValueError('No DjVu pages found')
    writer = QPdfWriter(os.path.join(work, 'result.pdf'))
    writer.setResolution(DPI)
    painter = QPainter()
    with_text = 0
    try:
        for number in range(1, count + 1):
            progress((number - 1) / count, f'DJVU → PDF: {number}/{count}')
            run(render, ['-format=ppm', f'-page={number}', f'-scale={DPI}', 'source.djvu', 'raster.ppm'], work)
            image = QImage(os.path.join(work, 'raster.ppm'))
            if image.isNull():
                raise ValueError('DjVu page rendering failed')
            width, height = image.width(), image.height()
            writer.setPageLayout(QPageLayout(QPageSize(QSizeF(width * 72 / DPI, height * 72 / DPI), QPageSize.Unit.Point),
                                            QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
            if number == 1:
                if not painter.begin(writer):
                    raise ValueError('Could not create PDF')
            elif not writer.newPage():
                raise ValueError('Could not create PDF page')
            raw = run(edit, ['-u', '-e', f'select {number}; print-txt', 'source.djvu'], work).decode('utf-8')
            trees = parse_text(raw)
            if trees and len(trees[0]) >= 5 and float(trees[0][3]) > 0 and float(trees[0][4]) > 0:
                tree = trees[0]
                sx, sy = width / float(tree[3]), height / float(tree[4])
                zones = list(text_zones(tree))
                if zones:
                    with_text += 1
                for (x0, y0, x1, y1), text in zones:
                    if x1 <= x0 or y1 <= y0:
                        continue
                    font = QFont('Arial')
                    font.setPixelSize(max(1, round((y1 - y0) * sy)))
                    painter.setFont(font)
                    metrics = QFontMetricsF(font)
                    painter.save()
                    painter.translate(x0 * sx, height - y1 * sy)
                    painter.scale((x1 - x0) * sx / max(1, metrics.horizontalAdvance(text)),
                                  (y1 - y0) * sy / max(1, metrics.height()))
                    painter.drawText(QPointF(0, metrics.ascent()), text)
                    painter.restore()
            # Paint an opaque page over the searchable text: it remains in PDF
            # for extraction/selection, without altering the visible scan.
            painter.drawImage(QRectF(0, 0, width, height), image)
    finally:
        if painter.isActive():
            painter.end()
    log(f'Text transferred on {with_text}/{count} pages. No OCR performed.')
    return 'result.pdf'


def convert_document(source, destination, input_format, progress, log):
    with TemporaryDirectory('_djvu_conversion') as work:
        ext = 'pdf' if input_format == 'pdf' else 'djvu'
        shutil.copyfile(source, os.path.join(work, 'source.' + ext))
        result = pdf_to_djvu(work, progress, log) if ext == 'pdf' else djvu_to_pdf(work, progress, log)
        shutil.copyfile(os.path.join(work, result), destination)
    progress(1.0, 'Conversion complete')
