#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.utils.img import image_from_data, scale_image, image_to_data, blend_on_canvas


def rescale_image(data, scale_news_images, compress_news_images_max_size, compress_news_images_auto_size):
    orig_data = data  # save it in case compression fails
    img = image_from_data(data)
    orig_w, orig_h = img.width(), img.height()
    if scale_news_images is not None:
        wmax, hmax = scale_news_images
        if wmax < orig_w or hmax < orig_h:
            orig_w, orig_h, data = scale_image(img, wmax, hmax, compression_quality=95)
    if compress_news_images_max_size is None:
        if compress_news_images_auto_size is None:  # not compressing
            return data
        maxsizeb = (orig_w * orig_h)/compress_news_images_auto_size
    else:
        maxsizeb = compress_news_images_max_size * 1024

    if len(data) <= maxsizeb:  # no compression required
        return data

    scaled_data = data  # save it in case compression fails
    quality = 90
    while len(data) >= maxsizeb and quality >= 5:
        data = image_to_data(image_from_data(scaled_data), compression_quality=quality)
        quality -= 5

    if len(data) >= len(scaled_data):  # compression failed
        return orig_data if len(orig_data) <= len(scaled_data) else scaled_data

    if len(data) >= len(orig_data):  # no improvement
        return orig_data

    return data


def prepare_masthead_image(path_to_image, out_path, mi_width, mi_height):
    with lopen(path_to_image, 'rb') as f:
        img = image_from_data(f.read())
    img = blend_on_canvas(img, mi_width, mi_height)
    with lopen(out_path, 'wb') as f:
        f.write(image_to_data(img))


if __name__ == '__main__':
    import sys
    data = sys.stdin.read()
    sys.stdout.write(rescale_image(data, (768, 1024), None, 8))
