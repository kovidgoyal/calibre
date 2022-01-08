__license__ = 'GPL 3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre.ptempfile import TemporaryDirectory
from calibre.constants import __appname__, __version__


class SNBOutput(OutputFormatPlugin):

    name = 'SNB Output'
    author = 'Li Fanxi'
    file_type = 'snb'
    commit_name = 'snb_output'

    options = {
        OptionRecommendation(name='snb_output_encoding', recommended_value='utf-8',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. '
            'The default is utf-8.')),
        OptionRecommendation(name='snb_max_line_length',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_('The maximum number of characters per line. This splits on '
            'the first space before the specified value. If no space is found '
            'the line will be broken at the space after and will exceed the '
            'specified value. Also, there is a minimum of 25 characters. '
            'Use 0 to disable line splitting.')),
        OptionRecommendation(name='snb_insert_empty_line',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Specify whether or not to insert an empty line between '
            'two paragraphs.')),
        OptionRecommendation(name='snb_dont_indent_first_line',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Specify whether or not to insert two space characters '
            'to indent the first line of each paragraph.')),
        OptionRecommendation(name='snb_hide_chapter_name',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Specify whether or not to hide the chapter title for each '
            'chapter. Useful for image-only output (eg. comics).')),
        OptionRecommendation(name='snb_full_screen',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Resize all the images for full screen mode. ')),
     }

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from lxml import etree
        from calibre.ebooks.snb.snbfile import SNBFile
        from calibre.ebooks.snb.snbml import SNBMLizer, ProcessFileName

        self.opts = opts
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer, Unavailable
        try:
            rasterizer = SVGRasterizer()
            rasterizer(oeb_book, opts)
        except Unavailable:
            log.warn('SVG rasterizer unavailable, SVG will not be converted')

        # Create temp dir
        with TemporaryDirectory('_snb_output') as tdir:
            # Create stub directories
            snbfDir = os.path.join(tdir, 'snbf')
            snbcDir = os.path.join(tdir, 'snbc')
            snbiDir = os.path.join(tdir, 'snbc/images')
            os.mkdir(snbfDir)
            os.mkdir(snbcDir)
            os.mkdir(snbiDir)

            # Process Meta data
            meta = oeb_book.metadata
            if meta.title:
                title = str(meta.title[0])
            else:
                title = ''
            authors = [str(x) for x in meta.creator if x.role == 'aut']
            if meta.publisher:
                publishers = str(meta.publisher[0])
            else:
                publishers = ''
            if meta.language:
                lang = str(meta.language[0]).upper()
            else:
                lang = ''
            if meta.description:
                abstract = str(meta.description[0])
            else:
                abstract = ''

            # Process Cover
            g, m, s = oeb_book.guide, oeb_book.manifest, oeb_book.spine
            href = None
            if 'titlepage' not in g:
                if 'cover' in g:
                    href = g['cover'].href

            # Output book info file
            bookInfoTree = etree.Element("book-snbf", version="1.0")
            headTree = etree.SubElement(bookInfoTree, "head")
            etree.SubElement(headTree, "name").text = title
            etree.SubElement(headTree, "author").text = ' '.join(authors)
            etree.SubElement(headTree, "language").text = lang
            etree.SubElement(headTree, "rights")
            etree.SubElement(headTree, "publisher").text = publishers
            etree.SubElement(headTree, "generator").text = __appname__ + ' ' + __version__
            etree.SubElement(headTree, "created")
            etree.SubElement(headTree, "abstract").text = abstract
            if href is not None:
                etree.SubElement(headTree, "cover").text = ProcessFileName(href)
            else:
                etree.SubElement(headTree, "cover")
            with open(os.path.join(snbfDir, 'book.snbf'), 'wb') as f:
                f.write(etree.tostring(bookInfoTree, pretty_print=True, encoding='utf-8'))

            # Output TOC
            tocInfoTree = etree.Element("toc-snbf")
            tocHead = etree.SubElement(tocInfoTree, "head")
            tocBody = etree.SubElement(tocInfoTree, "body")
            outputFiles = {}
            if oeb_book.toc.count() == 0:
                log.warn('This SNB file has no Table of Contents. '
                    'Creating a default TOC')
                first = next(iter(oeb_book.spine))
                oeb_book.toc.add(_('Start page'), first.href)
            else:
                first = next(iter(oeb_book.spine))
                if oeb_book.toc[0].href != first.href:
                    # The pages before the fist item in toc will be stored as
                    # "Cover Pages".
                    # oeb_book.toc does not support "insert", so we generate
                    # the tocInfoTree directly instead of modifying the toc
                    ch = etree.SubElement(tocBody, "chapter")
                    ch.set("src", ProcessFileName(first.href) + ".snbc")
                    ch.text = _('Cover pages')
                    outputFiles[first.href] = []
                    outputFiles[first.href].append(("", _("Cover pages")))

            for tocitem in oeb_book.toc:
                if tocitem.href.find('#') != -1:
                    item = tocitem.href.split('#')
                    if len(item) != 2:
                        log.error('Error in TOC item: %s' % tocitem)
                    else:
                        if item[0] in outputFiles:
                            outputFiles[item[0]].append((item[1], tocitem.title))
                        else:
                            outputFiles[item[0]] = []
                            if "" not in outputFiles[item[0]]:
                                outputFiles[item[0]].append(("", tocitem.title + _(" (Preface)")))
                                ch = etree.SubElement(tocBody, "chapter")
                                ch.set("src", ProcessFileName(item[0]) + ".snbc")
                                ch.text = tocitem.title + _(" (Preface)")
                            outputFiles[item[0]].append((item[1], tocitem.title))
                else:
                    if tocitem.href in outputFiles:
                        outputFiles[tocitem.href].append(("", tocitem.title))
                    else:
                        outputFiles[tocitem.href] = []
                        outputFiles[tocitem.href].append(("", tocitem.title))
                ch = etree.SubElement(tocBody, "chapter")
                ch.set("src", ProcessFileName(tocitem.href) + ".snbc")
                ch.text = tocitem.title

            etree.SubElement(tocHead, "chapters").text = '%d' % len(tocBody)

            with open(os.path.join(snbfDir, 'toc.snbf'), 'wb') as f:
                f.write(etree.tostring(tocInfoTree, pretty_print=True, encoding='utf-8'))

            # Output Files
            oldTree = None
            mergeLast = False
            lastName = None
            for item in s:
                from calibre.ebooks.oeb.base import OEB_DOCS, OEB_IMAGES
                if m.hrefs[item.href].media_type in OEB_DOCS:
                    if item.href not in outputFiles:
                        log.debug('File %s is unused in TOC. Continue in last chapter' % item.href)
                        mergeLast = True
                    else:
                        if oldTree is not None and mergeLast:
                            log.debug('Output the modified chapter again: %s' % lastName)
                            with open(os.path.join(snbcDir, lastName), 'wb') as f:
                                f.write(etree.tostring(oldTree, pretty_print=True, encoding='utf-8'))
                            mergeLast = False

                    log.debug('Converting %s to snbc...' % item.href)
                    snbwriter = SNBMLizer(log)
                    snbcTrees = None
                    if not mergeLast:
                        snbcTrees = snbwriter.extract_content(oeb_book, item, outputFiles[item.href], opts)
                        for subName in snbcTrees:
                            postfix = ''
                            if subName != '':
                                postfix = '_' + subName
                            lastName = ProcessFileName(item.href + postfix + ".snbc")
                            oldTree = snbcTrees[subName]
                            with open(os.path.join(snbcDir, lastName), 'wb') as f:
                                f.write(etree.tostring(oldTree, pretty_print=True, encoding='utf-8'))
                    else:
                        log.debug('Merge %s with last TOC item...' % item.href)
                        snbwriter.merge_content(oldTree, oeb_book, item, [('', _("Start"))], opts)

            # Output the last one if needed
            log.debug('Output the last modified chapter again: %s' % lastName)
            if oldTree is not None and mergeLast:
                with open(os.path.join(snbcDir, lastName), 'wb') as f:
                    f.write(etree.tostring(oldTree, pretty_print=True, encoding='utf-8'))
                mergeLast = False

            for item in m:
                if m.hrefs[item.href].media_type in OEB_IMAGES:
                    log.debug('Converting image: %s ...' % item.href)
                    content = m.hrefs[item.href].data
                    # Convert & Resize image
                    self.HandleImage(content, os.path.join(snbiDir, ProcessFileName(item.href)))

            # Package as SNB File
            snbFile = SNBFile()
            snbFile.FromDir(tdir)
            snbFile.Output(output_path)

    def HandleImage(self, imageData, imagePath):
        from calibre.utils.img import image_from_data, resize_image, image_to_data
        img = image_from_data(imageData)
        x, y = img.width(), img.height()
        if self.opts:
            if self.opts.snb_full_screen:
                SCREEN_X, SCREEN_Y = self.opts.output_profile.screen_size
            else:
                SCREEN_X, SCREEN_Y = self.opts.output_profile.comic_screen_size
        else:
            SCREEN_X = 540
            SCREEN_Y = 700
        # Handle big image only
        if x > SCREEN_X or y > SCREEN_Y:
            xScale = float(x) / SCREEN_X
            yScale = float(y) / SCREEN_Y
            scale = max(xScale, yScale)
            # TODO : intelligent image rotation
            #     img = img.rotate(90)
            #     x,y = y,x
            img = resize_image(img, x // scale, y // scale)
        with lopen(imagePath, 'wb') as f:
            f.write(image_to_data(img, fmt=imagePath.rpartition('.')[-1]))


if __name__ == '__main__':
    from calibre.ebooks.oeb.reader import OEBReader
    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
    from calibre.customize.profiles import HanlinV3Output

    class OptionValues:
        pass

    opts = OptionValues()
    opts.output_profile = HanlinV3Output(None)

    html_preprocessor = HTMLPreProcessor(None, None, opts)
    from calibre.utils.logging import default_log
    oeb = OEBBook(default_log, html_preprocessor)
    reader = OEBReader
    reader()(oeb, '/tmp/bbb/processed/')
    SNBOutput(None).convert(oeb, '/tmp/test.snb', None, None, default_log)
