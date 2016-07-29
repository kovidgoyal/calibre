# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Timothy Legge <timlegge@gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os


class Bookmark():  # {{{
    '''
    A simple class fetching bookmark data
    kobo-specific
    '''
    def __init__(self, db_connection, contentid, path, id, book_format, bookmark_extension):
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
        self.contentid = contentid
        self.percent_read = 0
        self.get_bookmark_data()
        self.get_book_length()          # Not Used

    def get_bookmark_data(self):
        ''' Return the timestamp and last_read_location '''
        user_notes = {}
        self.timestamp = os.path.getmtime(self.path)

        cursor = self.db_connection.cursor()
        t = (self.contentid,)

        kepub_chapter_query = (
                           'SELECT Title, volumeIndex '
                           'FROM content '
                           'WHERE ContentID LIKE ? '
                           )
        bookmark_query = ('SELECT bm.bookmarkid, bm.ContentID, bm.text, bm.annotation, '
                            'bm.ChapterProgress, bm.StartContainerChildIndex, bm.StartOffset, '
                            'c.BookTitle, c.TITLE, c.volumeIndex, c.MimeType '
                        'FROM Bookmark bm LEFT OUTER JOIN Content c ON '
                            'c.ContentID = bm.ContentID '
                        'WHERE bm.Hidden = "false" '
                            'AND bm.volumeid = ? '
                        'ORDER BY bm.ContentID, bm.chapterprogress')
        cursor.execute(bookmark_query, t)

        previous_chapter = 0
        bm_count = 0
        for row in cursor:
            current_chapter = row[9]
            chapter_title = row[8]
            # For kepubs on newer firmware, the title needs to come from an 899 row.
            if not row[10] or row[10] == 'application/xhtml+xml' or row[10] == 'application/x-kobo-epub+zip':
                cursor2 = self.db_connection.cursor()
                kepub_chapter_data = ('{0}-%'.format(row[1]), )
                cursor2.execute(kepub_chapter_query, kepub_chapter_data)
                try:
                    kepub_chapter = cursor2.next()
                    chapter_title = kepub_chapter[0]
                    current_chapter = kepub_chapter[1]
                except StopIteration:
                    pass
                finally:
                    cursor2.close
            if previous_chapter == current_chapter:
                bm_count = bm_count + 1
            else:
                bm_count = 0

            text = row[2]
            annotation = row[3]

            # A dog ear (bent upper right corner) is a bookmark
            if row[5] == row[6] == 0:   # StartContainerChildIndex = StartOffset = 0
                e_type = 'Bookmark'
                text = row[8]
            # highlight is text with no annotation
            elif text is not None and (annotation is None or annotation == ""):
                e_type = 'Highlight'
            elif text and annotation:
                e_type = 'Annotation'
            else:
                e_type = 'Unknown annotation type'

            note_id = current_chapter * 1000 + bm_count

            # book_title = row[8]
            chapter_progress = min(round(float(100*row[4]),2),100)
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

        cursor.execute('SELECT datelastread, ___PercentRead '
                        'FROM content '
                        'WHERE bookid IS NULL '
                        'AND ReadStatus > 0 '
                        'AND contentid = ?',
                        t)
        for row in cursor:
            self.last_read = row[0]
            self.percent_read = row[1]
            # print row[1]
        cursor.close()

#                self.last_read_location = self.last_read - self.pdf_page_offset
        self.user_notes = user_notes

    def get_book_length(self):
        # TL        self.book_length = 0
        # TL        self.book_length = int(unpack('>I', record0[0x04:0x08])[0])
        pass

# }}}
