# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Timothy Legge <timlegge@gmail.com> and Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from contextlib import closing


class Bookmark(): # {{{
    '''
    A simple class fetching bookmark data
    kobo-specific
    '''
    def __init__(self, db_path, contentid, path, id, book_format, bookmark_extension):
        self.book_format = book_format
        self.bookmark_extension = bookmark_extension
        self.book_length = 0            # Not Used
        self.id = id
        self.last_read = 0
        self.last_read_location = 0     # Not Used
        self.path = path
        self.timestamp = 0
        self.user_notes = None
        self.db_path = db_path
        self.contentid = contentid
        self.percent_read = 0
        self.get_bookmark_data()
        self.get_book_length()          # Not Used

    def get_bookmark_data(self):
        ''' Return the timestamp and last_read_location '''
        import sqlite3 as sqlite
        user_notes = {}
        self.timestamp = os.path.getmtime(self.path)
        with closing(sqlite.connect(self.db_path)) as connection:
            # return bytestrings if the content cannot the decoded as unicode
            connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")

            cursor = connection.cursor()
            t = (self.contentid,)

            cursor.execute('select bm.bookmarkid, bm.contentid, bm.volumeid, '
                                'bm.text, bm.annotation, bm.ChapterProgress, '
                                'bm.StartContainerChildIndex, bm.StartOffset, c.BookTitle, '
                                'c.TITLE, c.volumeIndex, c.___NumPages '
                            'from Bookmark bm inner join Content c on '
                                'bm.contentid = c.contentid and '
                                'bm.volumeid = ? order by bm.volumeid, bm.chapterprogress', t)

            previous_chapter = 0
            bm_count = 0
            for row in cursor:
                current_chapter = row[10]
                if previous_chapter == current_chapter:
                    bm_count = bm_count + 1
                else:
                    bm_count = 0

                text = row[3]
                annotation = row[4]

                # A dog ear (bent upper right corner) is a bookmark
                if row[6] == row[7] == 0:   # StartContainerChildIndex = StartOffset = 0
                    e_type = 'Bookmark'
                    text = row[9]
                # highlight is text with no annotation
                elif text is not None and (annotation is None or annotation == ""):
                    e_type = 'Highlight'
                elif text and annotation:
                    e_type = 'Annotation'
                else:
                    e_type = 'Unknown annotation type'

                note_id = row[10] + bm_count
                chapter_title = row[9]
                # book_title = row[8]
                chapter_progress = min(round(float(100*row[5]),2),100)
                user_notes[note_id] = dict(id=self.id,
                                        displayed_location=note_id,
                                        type=e_type,
                                        text=text,
                                        annotation=annotation,
                                        chapter=row[10],
                                        chapter_title=chapter_title,
                                        chapter_progress=chapter_progress)
                previous_chapter = row[10]
                # debug_print("e_type:" , e_type, '\t', 'loc: ', note_id, 'text: ', text,
                        # 'annotation: ', annotation, 'chapter_title: ', chapter_title,
                        # 'chapter_progress: ', chapter_progress, 'date: ')

            cursor.execute('select datelastread, ___PercentRead from content '
                                'where bookid is Null and '
                                'contentid = ?', t)
            for row in cursor:
                self.last_read = row[0]
                self.percent_read = row[1]
                # print row[1]
            cursor.close()

#                self.last_read_location = self.last_read - self.pdf_page_offset
        self.user_notes = user_notes


    def get_book_length(self):
#TL        self.book_length = 0
#TL        self.book_length = int(unpack('>I', record0[0x04:0x08])[0])
        pass

# }}}
