__license__   = 'GPL v3'
__copyright__ = '2011, Timothy Legge <timlegge@gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.devices.usbms.driver import debug_print


class Bookmark():  # {{{
    '''
    A simple class fetching bookmark data
    kobo-specific
    '''

    def __init__(self, db_connection, contentId, path, id, book_format, bookmark_extension):
        self.book_format = book_format
        self.bookmark_extension = bookmark_extension
        self.book_length = 0            # Not Used
        self.id = id
        self.last_read = 0
        self.last_read_location = 0     # Not Used
        self.path = path
        self.timestamp = 0
        self.user_notes = None
        self.db_connection = db_connection
        self.contentId = contentId
        self.percent_read = 0
        self.kepub = (self.contentId.endswith('.kepub.epub') or not os.path.splitext(self.contentId)[1])
        self.get_bookmark_data()
        self.get_book_length()          # Not Used

    def get_bookmark_data(self):
        ''' Return the timestamp and last_read_location '''
        user_notes = {}
        self.timestamp = os.path.getmtime(self.path)

        cursor = self.db_connection.cursor()
        book_query_values = (self.contentId,)

        kepub_chapter_query = (
            'SELECT c.ContentID, c.BookTitle, c.Title, c.VolumeIndex, c.___NumPages, c.MimeType '
            'FROM content c '
            'WHERE ContentType = 899 '
            'AND c.BookID = ? '
            'ORDER BY c.VolumeIndex'
        )
        bookmark_query = (
            'SELECT bm.BookmarkID, bm.ContentID, bm.Text, bm.Annotation, '
            'bm.ChapterProgress, bm.StartContainerChildIndex, bm.StartOffset, '
            'c.BookTitle, c.Title, c.volumeIndex, c.MimeType '
            'FROM Bookmark bm LEFT OUTER JOIN Content c ON c.ContentID = bm.ContentID '
            'WHERE bm.Hidden = "false" AND bm.volumeid = ? '
            'ORDER BY bm.ContentID, bm.chapterprogress'
        )

        debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub chapters: contentId={self.contentId}")
        cursor.execute(kepub_chapter_query, book_query_values)
        kepub_chapters = {}
        if self.kepub:
            try:
                for chapter_row in cursor:
                    chapter_contentID = chapter_row['ContentID']
                    chapter_contentID = chapter_contentID[:chapter_contentID.rfind('-')]
                    kepub_chapters[chapter_contentID] = {
                                                         'chapter_title': chapter_row['Title'],
                                                         'chapter_index': chapter_row['VolumeIndex']
                                                        }
                debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub chapter: kepub chapters={kepub_chapters}")
            except:
                debug_print("Kobo::Bookmark::get_bookmark_data - No chapters found")

        cursor.execute(bookmark_query, book_query_values)

        previous_chapter = 0
        bm_count = 0
        for row in cursor:
            current_chapter = row['VolumeIndex'] if row['VolumeIndex'] is not None else 0
            chapter_title = row['Title']
            # For kepubs on newer firmware, the title needs to come from an 899 row.
            if self.kepub:
                chapter_contentID = row['ContentID']
                debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub: chapter chapter_contentID='{chapter_contentID}'")
                filename_index = chapter_contentID.find('!')
                book_contentID_part = chapter_contentID[:filename_index]
                debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub: chapter book_contentID_part='{book_contentID_part}'")
                file_contentID_part = chapter_contentID[filename_index + 1:]
                filename_index = file_contentID_part.find('!')
                opf_reference = file_contentID_part[:filename_index]
                debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub: chapter opf_reference='{opf_reference}'")
                file_contentID_part = file_contentID_part[filename_index + 1:]
                debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub: chapter file_contentID_part='{file_contentID_part}'")
#                 from urllib import quote
#                 file_contentID_part = quote(file_contentID_part)
                chapter_contentID = book_contentID_part + "!" + opf_reference + "!" + file_contentID_part
                debug_print(f"Kobo::Bookmark::get_bookmark_data - getting kepub chapter chapter_contentID='{chapter_contentID}'")
                kepub_chapter = kepub_chapters.get(chapter_contentID, None)
                if kepub_chapter is not None:
                    chapter_title = kepub_chapter['chapter_title']
                    current_chapter = kepub_chapter['chapter_index']
                else:
                    chapter_title = ''
                    current_chapter = 0

            if previous_chapter == current_chapter:
                bm_count = bm_count + 1
            else:
                bm_count = 0

            text = row['Text']
            annotation = row['Annotation']

            # A dog ear (bent upper right corner) is a bookmark
            if row['StartContainerChildIndex'] == row['StartOffset'] == 0:   # StartContainerChildIndex = StartOffset = 0
                e_type = 'Bookmark'
                text = row['Title']
            # highlight is text with no annotation
            elif text is not None and (annotation is None or annotation == ""):
                e_type = 'Highlight'
            elif text and annotation:
                e_type = 'Annotation'
            else:
                e_type = 'Unknown annotation type'

            note_id = current_chapter * 1000 + bm_count

            # book_title = row[8]
            chapter_progress = min(round(float(100*row['ChapterProgress']),2),100)
            user_notes[note_id] = dict(id=self.id,
                                    displayed_location=note_id,
                                    type=e_type,
                                    text=text,
                                    annotation=annotation,
                                    chapter=current_chapter,
                                    chapter_title=chapter_title,
                                    chapter_progress=chapter_progress)
            previous_chapter = current_chapter
            # debug_print("e_type:" , e_type, '\t', 'loc: ', note_id, 'text: ', text,
            # 'annotation: ', annotation, 'chapter_title: ', chapter_title,
            # 'chapter_progress: ', chapter_progress, 'date: ')

        cursor.execute('SELECT DateLastRead, ___PercentRead, ReadStatus '
                        'FROM content '
                        'WHERE bookid IS NULL '
                        'AND ReadStatus > 0 '
                        'AND ContentID = ? '
                        'ORDER BY DateLastRead, ReadStatus',
                        book_query_values)
        for row in cursor:
            self.last_read = row['DateLastRead']
            self.percent_read = 100 if (row['ReadStatus'] == 2) else row['___PercentRead']
            # print row[1]
        cursor.close()

#                self.last_read_location = self.last_read - self.pdf_page_offset
        self.user_notes = user_notes

    def get_book_length(self):
        # TL        self.book_length = 0
        # TL        self.book_length = int(unpack('>I', record0[0x04:0x08])[0])
        pass

    def __str__(self):
        '''
        A string representation of this object, suitable for printing to
        console
        '''
        ans = ["Kobo bookmark:"]

        def fmt(x, y):
            ans.append('%-20s: %s'%(str(x), str(y)))

        if self.contentId:
            fmt('ContentID', self.contentId)
        if self.last_read:
            fmt('Last Read', self.last_read)
        if self.timestamp:
            fmt('Timestamp', self.timestamp)
        if self.percent_read:
            fmt('Percent Read', self.percent_read)
        if self.user_notes:
            fmt('User Notes', self.user_notes)

        ans = '\n'.join(ans) + "\n"

        return ans


# }}}
