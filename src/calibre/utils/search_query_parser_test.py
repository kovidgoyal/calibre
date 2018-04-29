#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import operator
import unittest

from calibre.utils.search_query_parser import SearchQueryParser, Parser


class Tester(SearchQueryParser):

    texts = {
 1: [u'Eugenie Grandet', u'Honor\xe9 de Balzac', u'manybooks.net', u'lrf'],
 2: [u'Fanny Hill', u'John Cleland', u'manybooks.net', u'lrf'],
 3: [u'Persuasion', u'Jane Austen', u'manybooks.net', u'lrf'],
 4: [u'Psmith, Journalist', u'P. G. Wodehouse', u'Some Publisher', u'lrf'],
 5: [u'The Complete Works of William Shakespeare',
     u'William Shakespeare',
     u'manybooks.net',
     u'lrf'],
 6: [u'The History of England, Volume I',
     u'David Hume',
     u'manybooks.net',
     u'lrf'],
 7: [u'Someone Comes to Town, Someone Leaves Town',
     u'Cory Doctorow',
     u'Tor Books',
     u'lrf'],
 8: [u'Stalky and Co.', u'Rudyard Kipling', u'manybooks.net', u'lrf'],
 9: [u'A Game of Thrones', u'George R. R. Martin', None, u'lrf,rar'],
 10: [u'A Clash of Kings', u'George R. R. Martin', None, u'lrf,rar'],
 11: [u'A Storm of Swords', u'George R. R. Martin', None, u'lrf,rar'],
 12: [u'Biggles - Pioneer Air Fighter', u'W. E. Johns', None, u'lrf,rtf'],
 13: [u'Biggles of the Camel Squadron',
      u'W. E. Johns',
      u'London:Thames, (1977)',
      u'lrf,rtf'],
 14: [u'A Feast for Crows', u'George R. R. Martin', None, u'lrf,rar'],
 15: [u'Cryptonomicon', u'Neal Stephenson', None, u'lrf,rar'],
 16: [u'Quicksilver', u'Neal Stephenson', None, u'lrf,zip'],
 17: [u'The Comedies of William Shakespeare',
      u'William Shakespeare',
      None,
      u'lrf'],
 18: [u'The Histories of William Shakespeare',
      u'William Shakespeare',
      None,
      u'lrf'],
 19: [u'The Tragedies of William Shakespeare',
      u'William Shakespeare',
      None,
      u'lrf'],
 20: [u'An Ideal Husband', u'Oscar Wilde', u'manybooks.net', u'lrf'],
 21: [u'Flight of the Nighthawks', u'Raymond E. Feist', None, u'lrf,rar'],
 22: [u'Into a Dark Realm', u'Raymond E. Feist', None, u'lrf,rar'],
 23: [u'The Sundering', u'Walter Jon Williams', None, u'lrf,rar'],
 24: [u'The Praxis', u'Walter Jon Williams', None, u'lrf,rar'],
 25: [u'Conventions of War', u'Walter Jon Williams', None, u'lrf,rar'],
 26: [u'Banewreaker', u'Jacqueline Carey', None, u'lrf,rar'],
 27: [u'Godslayer', u'Jacqueline Carey', None, u'lrf,rar'],
 28: [u"Kushiel's Scion", u'Jacqueline Carey', None, u'lrf,rar'],
 29: [u'Underworld', u'Don DeLillo', None, u'lrf,rar'],
 30: [u'Genghis Khan and The Making of the Modern World',
      u'Jack Weatherford Orc',
      u'Three Rivers Press',
      u'lrf,zip'],
 31: [u'The Best and the Brightest',
      u'David Halberstam',
      u'Modern Library',
      u'lrf,zip'],
 32: [u'The Killer Angels', u'Michael Shaara', None, u'html,lrf'],
 33: [u'Band Of Brothers', u'Stephen E Ambrose', None, u'lrf,txt'],
 34: [u'The Gates of Rome', u'Conn Iggulden', None, u'lrf,rar'],
 35: [u'The Death of Kings', u'Conn Iggulden', u'Bantam Dell', u'lit,lrf'],
 36: [u'The Field of Swords', u'Conn Iggulden', None, u'lrf,rar'],
 37: [u'Masterman Ready', u'Marryat, Captain Frederick', None, u'lrf'],
 38: [u'With the Lightnings',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lit,lrf'],
 39: [u'Lt. Leary, Commanding',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lit,lrf'],
 40: [u'The Far Side of The Stars',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lrf,rar'],
 41: [u'The Way to Glory',
      u'David Drake',
      u'Baen Publishing Enterprises',
      u'lrf,rar'],
 42: [u'Some Golden Harbor', u'David Drake', u'Baen Books', u'lrf,rar'],
 43: [u'Harry Potter And The Half-Blood Prince',
      u'J. K. Rowling',
      None,
      u'lrf,rar'],
 44: [u'Harry Potter and the Order of the Phoenix',
      u'J. K. Rowling',
      None,
      u'lrf,rtf'],
 45: [u'The Stars at War', u'David Weber , Steve White', None, u'lrf,rtf'],
 46: [u'The Stars at War II',
      u'Steve White',
      u'Baen Publishing Enterprises',
      u'lrf,rar'],
 47: [u'Exodus', u'Steve White,Shirley Meier', u'Baen Books', u'lrf,rar'],
 48: [u'Harry Potter and the Goblet of Fire',
      u'J. K. Rowling',
      None,
      u'lrf,rar'],
 49: [u'Harry Potter and the Prisoner of Azkaban',
      u'J. K. Rowling',
      None,
      u'lrf,rtf'],
 50: [u'Harry Potter and the Chamber of Secrets',
      u'J. K. Rowling',
      None,
      u'lit,lrf'],
 51: [u'Harry Potter and the Deathly Hallows',
      u'J.K. Rowling',
      None,
      u'lit,lrf,pdf'],
 52: [u"His Majesty's Dragon", u'Naomi Novik', None, u'lrf,rar'],
 53: [u'Throne of Jade', u'Naomi Novik', u'Del Rey', u'lit,lrf'],
 54: [u'Black Powder War', u'Naomi Novik', u'Del Rey', u'lrf,rar'],
 55: [u'War and Peace', u'Leo Tolstoy', u'gutenberg.org', u'lrf,txt'],
 56: [u'Anna Karenina', u'Leo Tolstoy', u'gutenberg.org', u'lrf,txt'],
 57: [u'A Shorter History of Rome',
      u'Eugene Lawrence,Sir William Smith',
      u'gutenberg.org',
      u'lrf,zip'],
 58: [u'The Name of the Rose', u'Umberto Eco', None, u'lrf,rar'],
 71: [u"Wind Rider's Oath", u'David Weber', u'Baen', u'lrf'],
 74: [u'Rally Cry', u'William R Forstchen', None, u'htm,lrf'],
 86: [u'Empire of Ivory', u'Naomi Novik', None, u'lrf,rar'],
 87: [u"Renegade's Magic", u'Robin Hobb', None, u'lrf,rar'],
 89: [u'Master and commander',
      u"Patrick O'Brian",
      u'Fontana,\n1971',
      u'lit,lrf'],
 91: [u'A Companion to Wolves',
      u'Sarah Monette,Elizabeth Beär',
      None,
      u'lrf,rar'],
 92: [u'The Lions of al-Rassan', u'Guy Gavriel Kay', u'Eos', u'lit,lrf'],
 93: [u'Gardens of the Moon', u'Steven Erikson', u'Tor Fantasy', u'lit,lrf'],
 95: [u'The Master and Margarita',
      u'Mikhail Bulgakov',
      u'N.Y. : Knopf, 1992.',
      u'lrf,rtf'],
 120: [u'Deadhouse Gates',
       u'Steven Erikson',
       u'London : Bantam Books, 2001.',
       u'lit,lrf'],
 121: [u'Memories of Ice', u'Steven Erikson', u'Bantam Books', u'lit,lrf'],
 123: [u'House of Chains', u'Steven Erikson', u'Bantam Books', u'lit,lrf'],
 125: [u'Midnight Tides', u'Steven Erikson', u'Bantam Books', u'lit,lrf'],
 126: [u'The Bonehunters', u'Steven Erikson', u'Bantam Press', u'lit,lrf'],
 129: [u'Guns, germs, and steel: the fates of human societies',
       u'Jared Diamond',
       u'New York : W.W. Norton, c1997.',
       u'lit,lrf'],
 136: [u'Wildcards', u'George R. R. Martin', None, u'html,lrf'],
 138: [u'Off Armageddon Reef', u'David Weber', u'Tor Books', u'lit,lrf'],
 144: [u'Atonement',
       u'Ian McEwan',
       u'New York : Nan A. Talese/Doubleday, 2002.',
       u'lrf,rar'],
 146: [u'1632', u'Eric Flint', u'Baen Books', u'lit,lrf'],
 147: [u'1633', u'David Weber,Eric Flint,Dru Blair', u'Baen', u'lit,lrf'],
 148: [u'1634: The Baltic War',
       u'David Weber,Eric Flint',
       u'Baen',
       u'lit,lrf'],
 150: [u'The Dragonbone Chair', u'Tad Williams', u'DAW Trade', u'lrf,rtf'],
 152: [u'The Little Book That Beats the Market',
       u'Joel Greenblatt',
       u'Wiley',
       u'epub,lrf'],
 153: [u'Pride of Carthage', u'David Anthony Durham', u'Anchor', u'lit,lrf'],
 154: [u'Stone of farewell',
       u'Tad Williams',
       u'New York : DAW Books, 1990.',
       u'lrf,txt'],
 166: [u'American Gods', u'Neil Gaiman', u'HarperTorch', u'lit,lrf'],
 176: [u'Pillars of the Earth',
       u'Ken Follett',
       u'New American Library',
       u'lit,lrf'],
 182: [u'The Eye of the world',
       u'Robert Jordan',
       u'New York : T. Doherty Associates, c1990.',
       u'lit,lrf'],
 188: [u'The Great Hunt', u'Robert Jordan', u'ATOM', u'lrf,zip'],
 189: [u'The Dragon Reborn', u'Robert Jordan', None, u'lit,lrf'],
 190: [u'The Shadow Rising', u'Robert Jordan', None, u'lit,lrf'],
 191: [u'The Fires of Heaven',
       u'Robert Jordan',
       u'Time Warner Books Uk',
       u'lit,lrf'],
 216: [u'Lord of chaos',
       u'Robert Jordan',
       u'New York : TOR, c1994.',
       u'lit,lrf'],
 217: [u'A Crown of Swords', u'Robert Jordan', None, u'lit,lrf'],
 236: [u'The Path of Daggers', u'Robert Jordan', None, u'lit,lrf'],
 238: [u'The Client',
       u'John Grisham',
       u'New York : Island, 1994, c1993.',
       u'lit,lrf'],
 240: [u"Winter's Heart", u'Robert Jordan', None, u'lit,lrf'],
 242: [u'In the Beginning was the Command Line',
       u'Neal Stephenson',
       None,
       u'lrf,txt'],
 249: [u'Crossroads of Twilight', u'Robert Jordan', None, u'lit,lrf'],
 251: [u'Caves of Steel', u'Isaac Asimov', u'Del Rey', u'lrf,zip'],
 253: [u"Hunter's Run",
       u'George R. R. Martin,Gardner Dozois,Daniel Abraham',
       u'Eos',
       u'lrf,rar'],
 257: [u'Knife of Dreams', u'Robert Jordan', None, u'lit,lrf'],
 258: [u'Saturday',
       u'Ian McEwan',
       u'London : Jonathan Cape, 2005.',
       u'lrf,txt'],
 259: [u'My name is Red',
       u'Orhan Pamuk; translated from the Turkish by Erda\u011f G\xf6knar',
       u'New York : Alfred A. Knopf, 2001.',
       u'lit,lrf'],
 265: [u'Harbinger', u'David Mack', u'Star Trek', u'lit,lrf'],
 267: [u'Summon the Thunder',
       u'Dayton Ward,Kevin Dilmore',
       u'Pocket Books',
       u'lit,lrf'],
 268: [u'Shalimar the Clown',
       u'Salman Rushdie',
       u'New York : Random House, 2005.',
       u'lit,lrf'],
 269: [u'Reap the Whirlwind', u'David Mack', u'Star Trek', u'lit,lrf'],
 272: [u'Mistborn', u'Brandon Sanderson', u'Tor Fantasy', u'lrf,rar'],
 273: [u'The Thousandfold Thought',
       u'R. Scott Bakker',
       u'Overlook TP',
       u'lrf,rtf'],
 276: [u'Elantris',
       u'Brandon Sanderson',
       u'New York : Tor, 2005.',
       u'lrf,rar'],
 291: [u'Sundiver',
       u'David Brin',
       u'New York : Bantam Books, 1995.',
       u'lit,lrf'],
 299: [u'Imperium', u'Robert Harris', u'Arrow', u'lrf,rar'],
 300: [u'Startide Rising', u'David Brin', u'Bantam', u'htm,lrf'],
 301: [u'The Uplift War', u'David Brin', u'Spectra', u'lit,lrf'],
 304: [u'Brightness Reef', u'David Brin', u'Orbit', u'lrf,rar'],
 305: [u"Infinity's Shore", u'David Brin', u'Spectra', u'txt'],
 306: [u"Heaven's Reach", u'David Brin', u'Spectra', u'lrf,rar'],
 325: [u"Foundation's Triumph", u'David Brin', u'Easton Press', u'lit,lrf'],
 327: [u'I am Charlotte Simmons', u'Tom Wolfe', u'Vintage', u'htm,lrf'],
 335: [u'The Currents of Space', u'Isaac Asimov', None, u'lit,lrf'],
 340: [u'The Other Boleyn Girl',
       u'Philippa Gregory',
       u'Touchstone',
       u'lit,lrf'],
 341: [u"Old Man's War", u'John Scalzi', u'Tor', u'htm,lrf'],
 342: [u'The Ghost Brigades',
       u'John Scalzi',
       u'Tor Science Fiction',
       u'html,lrf'],
 343: [u'The Last Colony', u'John S"calzi', u'Tor Books', u'html,lrf'],
 344: [u'Gossip Girl', u'Cecily von Ziegesar', u'Warner Books', u'lrf,rtf'],
 347: [u'Little Brother', u'Cory Doctorow', u'Tor Teen', u'lrf'],
 348: [u'The Reality Dysfunction',
       u'Peter F. Hamilton',
       u'Pan MacMillan',
       u'lit,lrf'],
 353: [u'A Thousand Splendid Suns',
       u'Khaled Hosseini',
       u'Center Point Large Print',
       u'lit,lrf'],
 354: [u'Amsterdam', u'Ian McEwan', u'Anchor', u'lrf,txt'],
 355: [u'The Neutronium Alchemist',
       u'Peter F. Hamilton',
       u'Aspect',
       u'lit,lrf'],
 356: [u'The Naked God', u'Peter F. Hamilton', u'Aspect', u'lit,lrf'],
 421: [u'A Shadow in Summer', u'Daniel Abraham', u'Tor Fantasy', u'lrf,rar'],
 427: [u'Lonesome Dove', u'Larry M\\cMurtry', None, u'lit,lrf'],
 440: [u'Ghost', u'John Ringo', u'Baen', u'lit,lrf'],
 441: [u'Kildar', u'John Ringo', u'Baen', u'lit,lrf'],
 443: [u'Hidden Empire ', u'Kevin J. Anderson', u'Aspect', u'lrf,rar'],
 444: [u'The Gun Seller',
       u'Hugh Laurie',
       u'Washington Square Press',
       u'lrf,rar']
 }

    tests = {
             'Dysfunction' : set([348]),
             'title:Dysfunction' : set([348]),
             'Title:Dysfunction' : set([348]),
             'title:Dysfunction OR author:Laurie': set([348, 444]),
             '(tag:txt or tag:pdf)': set([33, 258, 354, 305, 242, 51, 55, 56, 154]),
             '(tag:txt OR tag:pdf) and author:Tolstoy': set([55, 56]),
             'Tolstoy txt': set([55, 56]),
             'Hamilton Amsterdam' : set([]),
             u'Beär' : set([91]),
             'dysfunc or tolstoy': set([348, 55, 56]),
             'tag:txt AND NOT tolstoy': set([33, 258, 354, 305, 242, 154]),
             'not tag:lrf' : set([305]),
             'london:thames': set([13]),
             'publisher:london:thames': set([13]),
             '"(1977)"': set([13]),
             'jack weatherford orc': set([30]),
             'S\\"calzi': {343},
             'author:S\\"calzi': {343},
             '"S\\"calzi"': {343},
             'M\\\\cMurtry': {427},
             'author:Tolstoy (tag:txt OR tag:pdf)': set([55, 56]),
             }
    fields = {'title':0, 'author':1, 'publisher':2, 'tag':3}

    _universal_set = set(texts.keys())

    def universal_set(self):
        return self._universal_set

    def get_matches(self, location, query, candidates=None):
        location = location.lower()
        if location in self.fields.keys():
            getter = operator.itemgetter(self.fields[location])
        elif location == 'all':
            getter = lambda y: ''.join(x if x else '' for x in y)
        else:
            getter = lambda x: ''

        if not query:
            return set([])
        query = query.lower()
        if candidates:
            return set(key for key, val in self.texts.items()
                if key in candidates and query and query
                        in getattr(getter(val), 'lower', lambda : '')())
        else:
            return set(key for key, val in self.texts.items()
                if query and query in getattr(getter(val), 'lower', lambda : '')())

    def run_tests(self, ae):
        for query in self.tests.keys():
            res = self.parse(query)
            ae(self.tests[query], res, 'Failed for query: {}'.format(query))


class TestSQP(unittest.TestCase):

    def do_test(self, optimize=False):
        tester = Tester(['authors', 'author', 'series', 'formats', 'format',
            'publisher', 'rating', 'tags', 'tag', 'comments', 'comment', 'cover',
            'isbn', 'ondevice', 'pubdate', 'size', 'date', 'title', u'#read',
            'all', 'search'], test=True, optimize=optimize)
        tester.run_tests(self.assertEqual)

    def test_sqp_optimized(self):
        self.do_test(True)

    def test_sqp_unoptimized(self):
        self.do_test(False)

    def test_sqp_tokenizer(self):
        p = Parser()

        def tokens(*a):
            ans = []
            for i in range(0, len(a), 2):
                ans.append(({'O': Parser.OPCODE, 'W': Parser.WORD, 'Q': Parser.QUOTED_WORD}[a[i]], a[i+1]))
            return ans

        def t(query, *a):
            self.assertEqual(tokens(*a), p.tokenize(query))

        t('xxx', 'W', 'xxx')
        t('"a \\" () b"', 'Q', 'a " () b')
        t('"a“b"', 'Q', 'a“b')
        t('"a”b"', 'Q', 'a”b')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSQP)


class TestRunner(unittest.main):

    def createTests(self):
        self.test = find_tests()


def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)


if __name__ == '__main__':
    run()
