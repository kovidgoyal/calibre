#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from calibre.customize import Plugin

class Source(Plugin):

    type = _('Metadata source')
    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    result_of_identify_is_complete = True

    def get_author_tokens(self, authors):
        'Take a list of authors and return a list of tokens useful for a '
        'AND search query'
        # Leave ' in there for Irish names
        pat = re.compile(r'[-,:;+!@#$%^&*(){}.`~"\s\[\]/]')
        for au in authors:
            for tok in au.split():
                yield pat.sub('', tok)

    def split_jobs(self, jobs, num):
        'Split a list of jobs into at most num groups, as evenly as possible'
        groups = [[] for i in range(num)]
        jobs = list(jobs)
        while jobs:
            for gr in groups:
                try:
                    job = jobs.pop()
                except IndexError:
                    break
                gr.append(job)
        return [g for g in groups if g]

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}):
        '''
        Identify a book by its title/author/isbn/etc.

        :param log: A log object, use it to output debugging information/errors
        :param result_queue: A result Queue, results should be put into it.
                            Each result is a Metadata object
        :param abort: If abort.is_set() returns True, abort further processing
                      and return as soon as possible
        :param title: The title of the book, can be None
        :param authors: A list of authors of the book, can be None
        :param identifiers: A dictionary of other identifiers, most commonly
                            {'isbn':'1234...'}
        :return: None if no errors occurred, otherwise a unicode representation
                 of the error suitable for showing to the user

        '''
        return None

