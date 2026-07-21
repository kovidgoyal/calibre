#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import os
import tempfile
from functools import partial
from queue import Empty, Queue
from threading import Event, Thread

from calibre import detect_ncpus, filesystem_encoding, force_unicode, human_readable
from calibre.utils.localization import _, ngettext


class Worker(Thread):

    daemon = True

    def __init__(self, abort, name, queue, results, jpeg_quality, webp_quality, progress_callback):
        Thread.__init__(self, name=name)
        self.queue, self.results = queue, results
        self.progress_callback = progress_callback
        self.jpeg_quality = jpeg_quality
        self.webp_quality = webp_quality
        self.abort = abort
        self.start()

    def run(self):
        while not self.abort.is_set():
            try:
                name, path, mt = self.queue.get_nowait()
            except Empty:
                break
            try:
                self.compress(name, path, mt)
            except Exception:
                import traceback
                self.results[name] = (False, traceback.format_exc())
            finally:
                try:
                    self.progress_callback(name)
                except Exception:
                    import traceback
                    traceback.print_exc()
                self.queue.task_done()

    def compress(self, name, path, mime_type):
        from calibre.utils.img import encode_jpeg, encode_webp, optimize_jpeg, optimize_png, optimize_webp
        if 'png' in mime_type:
            func = optimize_png
        elif 'webp' in mime_type:
            if self.webp_quality is None:
                func = optimize_webp
            else:
                func = partial(encode_webp, quality=self.jpeg_quality)
        elif self.jpeg_quality is None:
            func = optimize_jpeg
        else:
            func = partial(encode_jpeg, quality=self.jpeg_quality)
        before = os.path.getsize(path)
        with open(path, 'rb') as f:
            old_data = f.read()
        func(path)
        after = os.path.getsize(path)
        if after >= before:
            with open(path, 'wb') as f:
                f.write(old_data)
            after = before
        self.results[name] = (True, (before, after))


def get_compressible_images(container):
    mt_map = container.manifest_type_map
    images = set()
    for mt in 'png jpg jpeg webp'.split():
        images |= set(mt_map.get('image/' + mt, ()))
    return images


def convert_png_to_format(container, name, fmt, jpeg_quality=75, webp_quality=75, report=None):
    """Convert a PNG image in the container to JPEG or WEBP format.

    :param fmt: ``'jpeg'``, ``'webp'`` (lossy), or ``'webp-lossless'``
    :returns: ``(new_name, before, after)`` where *before* and *after* are the
        file sizes in bytes before and after conversion, or ``(name, 0, 0)`` if
        conversion was skipped.
    """
    from calibre.ebooks.oeb.polish.replace import rename_files
    from calibre.utils.img import image_from_data, image_to_data

    if fmt == 'jpeg':
        new_ext = 'jpg'
        new_mt = 'image/jpeg'
        img_fmt = 'JPEG'
        quality = jpeg_quality
    elif fmt == 'webp':
        new_ext = 'webp'
        new_mt = 'image/webp'
        img_fmt = 'WEBP'
        quality = webp_quality
    elif fmt == 'webp-lossless':
        new_ext = 'webp'
        new_mt = 'image/webp'
        img_fmt = 'WEBP'
        quality = 100  # quality=100 means lossless for WEBP in image_to_data
    else:
        return name, 0, 0

    base = name.rsplit('.', 1)[0] if '.' in name else name
    new_name = f'{base}.{new_ext}'

    if new_name != name and container.exists(new_name):
        if report:
            report(_('Skipping conversion of {0} as {1} already exists').format(name, new_name))
        return name, 0, 0

    path = container.get_file_path_for_processing(name)
    before = os.path.getsize(path)
    with open(path, 'rb') as f:
        original_data = f.read()

    img = image_from_data(original_data)
    new_data = image_to_data(img, compression_quality=quality, fmt=img_fmt)
    after = len(new_data)

    # Write to a temp file in the same directory, then atomically replace the original
    path_dir = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=path_dir)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(new_data)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    if new_name != name:
        rename_files(container, {name: new_name})
        container.mime_map[new_name] = new_mt
        for itemid, q in container.manifest_id_map.items():
            if q == new_name:
                for item in container.opf_xpath(f'//opf:manifest/opf:item[@href and @id="{itemid}"]'):
                    item.set('media-type', new_mt)
        container.dirty(container.opf_name)

    if report:
        if before != after:
            report(_('{0} converted to {1} [{2} {5} {3}, {4:.1%} reduction]').format(
                name, new_name, human_readable(before), human_readable(after), (before - after) / before, '→'))
        else:
            report(_('{0} converted to {1} [no size change]').format(name, new_name))

    return new_name, before, after


def compress_images(container, report=None, names=None, jpeg_quality=None, webp_quality=None, compress_png=True,
                    png_to_format=None, progress_callback=lambda n, t, name:True):
    images = get_compressible_images(container)
    if names is not None:
        images &= set(names)

    # Convert PNG images to the target format before any other compression
    conv_before_total = conv_after_total = conv_num = 0
    if png_to_format:
        png_images = sorted(name for name in images if container.mime_map.get(name) == 'image/png')
        j_quality = jpeg_quality if jpeg_quality is not None else 75
        w_quality = webp_quality if webp_quality is not None else 75
        for name in png_images:
            new_name, before, after = convert_png_to_format(
                container, name, png_to_format,
                jpeg_quality=j_quality, webp_quality=w_quality,
                report=report)
            if new_name != name:
                images.discard(name)
                images.add(new_name)
            if before:
                conv_num += 1
                conv_before_total += before
                conv_after_total += after

    if not compress_png:
        images = {name for name in images if container.mime_map.get(name) != 'image/png'}
    results = {}
    queue = Queue()
    abort = Event()
    seen = set()
    num_to_process = 0
    for name in sorted(images):
        path = os.path.abspath(container.get_file_path_for_processing(name))
        path_key = os.path.normcase(path)
        if path_key not in seen:
            num_to_process += 1
            queue.put((name, path, container.mime_map[name]))
            seen.add(path_key)

    def pc(name):
        keep_going = progress_callback(len(results), num_to_process, name)
        if not keep_going:
            abort.set()
    progress_callback(0, num_to_process, '')
    [Worker(abort, f'CompressImage{i}', queue, results, jpeg_quality, webp_quality, pc) for i in range(min(detect_ncpus(), num_to_process))]
    queue.join()
    before_total = after_total = 0
    processed_num = 0
    changed = conv_num > 0
    for name, (ok, res) in results.items():
        name = force_unicode(name, filesystem_encoding)
        if ok:
            before, after = res
            if before != after:
                changed = True
                processed_num += 1
            before_total += before
            after_total += after
            if report:
                if before != after:
                    report(_('{0} compressed from {1} to {2} bytes [{3:.1%} reduction]').format(
                        name, human_readable(before), human_readable(after), (before - after)/before))
                else:
                    report(_('{0} could not be further compressed').format(name))
        elif report:
            report(_('Failed to process {0} with error:').format(name))
            report(res)
    if report:
        if conv_num:
            report('')
            if conv_before_total and conv_before_total != conv_after_total:
                report(ngettext(
                    'PNG conversion: {0} file converted, total size changed from {1} to {2} [{3:.1%} reduction]',
                    'PNG conversion: {0} files converted, total size changed from {1} to {2} [{3:.1%} reduction]',
                    conv_num).format(conv_num, human_readable(conv_before_total), human_readable(conv_after_total),
                                     (conv_before_total - conv_after_total) / conv_before_total))
            else:
                report(ngettext(
                    'PNG conversion: {0} file converted, no size change',
                    'PNG conversion: {0} files converted, no size change',
                    conv_num).format(conv_num))
        grand_before = before_total + conv_before_total
        grand_after = after_total + conv_after_total
        grand_changed = processed_num + conv_num
        if grand_before and grand_changed:
            report('')
            report(_('Total image filesize reduced from {0} to {1} [{2:.1%} reduction, {3} images changed]').format(
                human_readable(grand_before), human_readable(grand_after), (grand_before - grand_after)/grand_before, grand_changed))
        elif not grand_changed:
            report(_('Images are already fully optimized'))
    return changed, results


def remove_unused_images(container, report=None):
    """
    Remove images that are not referenced by any file in the spine or by any
    stylesheet used by files in the spine.
    """
    report = report or (lambda x: x)
    from calibre.ebooks.oeb.polish.container import OEB_STYLES
    from calibre.ebooks.oeb.polish.report import safe_href_to_name

    # Collect spine document names
    spine_docs = {name for name, _ in container.spine_names}

    # Collect stylesheets referenced by spine documents
    used_stylesheets = set()
    for name in spine_docs:
        if not container.exists(name):
            continue
        root = container.parsed(name)
        for link in root.xpath('//*[local-name()="link" and @href]'):
            sname = safe_href_to_name(container, link.get('href'), name)
            if sname and container.exists(sname):
                mt = container.mime_map.get(sname, '')
                if mt in OEB_STYLES:
                    used_stylesheets.add(sname)

    # Collect all images referenced by spine docs and their stylesheets
    relevant_sources = spine_docs | used_stylesheets
    referenced_images = set()
    for source_name in relevant_sources:
        if not container.exists(source_name):
            continue
        for href, _line_number, _offset in container.iterlinks(source_name):
            target = safe_href_to_name(container, href, source_name)
            if target and container.exists(target):
                mt = container.mime_map.get(target, '')
                if mt and mt.startswith('image/'):
                    referenced_images.add(target)

    # Find all images in the container and remove unused ones
    all_images = {name for name, mt in container.mime_map.items() if mt.startswith('image/') and container.exists(name)}
    unused_images = all_images - referenced_images

    if not unused_images:
        report(_('No unused images found'))
        return False

    for name in sorted(unused_images):
        report(_('Removing unused image: {}').format(name))
        container.remove_item(name)

    report('')
    num = len(unused_images)
    report(ngettext('Removed one unused image', 'Removed {} unused images', num).format(num))
    return True
