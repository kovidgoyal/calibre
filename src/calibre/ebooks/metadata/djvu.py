# License: GPLv3
"""Render DjVu covers with the separately installed DjVuLibre tools."""

import os
import shutil
import subprocess

from calibre.constants import iswindows
from calibre.ebooks.metadata import MetaInformation
from calibre.ptempfile import TemporaryDirectory


def find_ddjvu():
    override = os.environ.get('CALIBRE_DDJVU')
    if override:
        if os.path.isfile(override):
            return override
        raise FileNotFoundError('CALIBRE_DDJVU does not point to ddjvu')
    found = shutil.which('ddjvu')
    if found:
        return found
    if iswindows:
        for key in ('ProgramFiles', 'ProgramFiles(x86)'):
            root = os.environ.get(key)
            if root:
                path = os.path.join(root, 'DjVuLibre', 'ddjvu.exe')
                if os.path.isfile(path):
                    return path
    raise FileNotFoundError('Install DjVuLibre, or set CALIBRE_DDJVU to the ddjvu executable')


def page_images(path, outputdir, first=1, last=1):
    from qt.core import QImage

    if first < 1 or last < first:
        raise ValueError('Invalid DjVu page range')
    executable = find_ddjvu()
    os.makedirs(outputdir, exist_ok=True)
    # ASCII filenames also work with older Windows builds of DjVuLibre.
    with TemporaryDirectory('_djvu_render') as work:
        shutil.copyfile(path, os.path.join(work, 'source.djvu'))
        result = subprocess.run(
            [executable, '-format=ppm', '-size=1200x1600', f'-page={first}-{last}',
             '-eachpage', 'source.djvu', 'page-%06d.ppm'],
            cwd=work, capture_output=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if iswindows else 0,
        )
        if result.returncode:
            raise ValueError('DjVu rendering failed: ' + result.stderr.decode('utf-8', 'replace')[-2000:])
        paths = []
        for name in sorted(os.listdir(work)):
            if not name.endswith('.ppm'):
                continue
            # ddjvu clamps an out-of-range request to the last page.
            # Do not append that page again when the user asks for more.
            number = int(name[5:-4])
            if not first <= number <= last:
                continue
            image = QImage(os.path.join(work, name))
            dest = os.path.join(outputdir, name[:-4] + '.jpg')
            if image.isNull() or not image.save(dest, 'JPEG', 90):
                raise ValueError('Could not read the rendered DjVu page')
            paths.append(dest)
        return paths


def get_metadata(stream, cover=True):
    mi = MetaInformation(None, None)
    if cover:
        with TemporaryDirectory('_djvu_cover') as work:
            path = os.path.join(work, 'input.djvu')
            stream.seek(0)
            with open(path, 'wb') as output:
                shutil.copyfileobj(stream, output)
            pages = page_images(path, work)
            if pages:
                with open(pages[0], 'rb') as image:
                    mi.cover_data = ('jpeg', image.read())
    return mi
