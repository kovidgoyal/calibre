#!/usr/bin/env python
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>


import operator
import unittest

from calibre.utils.search_query_parser import SearchQueryParser, Parser


class Tester(SearchQueryParser):

    texts = {
 1: ['Eugenie Grandet', 'Honor\xe9 de Balzac', 'manybooks.net', 'lrf'],
 2: ['Fanny Hill', 'John Cleland', 'manybooks.net', 'lrf'],
 3: ['Persuasion', 'Jane Austen', 'manybooks.net', 'lrf'],
 4: ['Psmith, Journalist', 'P. G. Wodehouse', 'Some Publisher', 'lrf'],
 5: ['The Complete Works of William Shakespeare',
     'William Shakespeare',
     'manybooks.net',
     'lrf'],
 6: ['The History of England, Volume I',
     'David Hume',
     'manybooks.net',
     'lrf'],
 7: ['Someone Comes to Town, Someone Leaves Town',
     'Cory Doctorow',
     'Tor Books',
     'lrf'],
 8: ['Stalky and Co.', 'Rudyard Kipling', 'manybooks.net', 'lrf'],
 9: ['A Game of Thrones', 'George R. R. Martin', None, 'lrf,rar'],
 10: ['A Clash of Kings', 'George R. R. Martin', None, 'lrf,rar'],
 11: ['A Storm of Swords', 'George R. R. Martin', None, 'lrf,rar'],
 12: ['Biggles - Pioneer Air Fighter', 'W. E. Johns', None, 'lrf,rtf'],
 13: ['Biggles of the Camel Squadron',
      'W. E. Johns',
      'London:Thames, (1977)',
      'lrf,rtf'],
 14: ['A Feast for Crows', 'George R. R. Martin', None, 'lrf,rar'],
 15: ['Cryptonomicon', 'Neal Stephenson', None, 'lrf,rar'],
 16: ['Quicksilver', 'Neal Stephenson', None, 'lrf,zip'],
 17: ['The Comedies of William Shakespeare',
      'William Shakespeare',
      None,
      'lrf'],
 18: ['The Histories of William Shakespeare',
      'William Shakespeare',
      None,
      'lrf'],
 19: ['The Tragedies of William Shakespeare',
      'William Shakespeare',
      None,
      'lrf'],
 20: ['An Ideal Husband', 'Oscar Wilde', 'manybooks.net', 'lrf'],
 21: ['Flight of the Nighthawks', 'Raymond E. Feist', None, 'lrf,rar'],
 22: ['Into a Dark Realm', 'Raymond E. Feist', None, 'lrf,rar'],
 23: ['The Sundering', 'Walter Jon Williams', None, 'lrf,rar'],
 24: ['The Praxis', 'Walter Jon Williams', None, 'lrf,rar'],
 25: ['Conventions of War', 'Walter Jon Williams', None, 'lrf,rar'],
 26: ['Banewreaker', 'Jacqueline Carey', None, 'lrf,rar'],
 27: ['Godslayer', 'Jacqueline Carey', None, 'lrf,rar'],
 28: ["Kushiel's Scion", 'Jacqueline Carey', None, 'lrf,rar'],
 29: ['Underworld', 'Don DeLillo', None, 'lrf,rar'],
 30: ['Genghis Khan and The Making of the Modern World',
      'Jack Weatherford Orc',
      'Three Rivers Press',
      'lrf,zip'],
 31: ['The Best and the Brightest',
      'David Halberstam',
      'Modern Library',
      'lrf,zip'],
 32: ['The Killer Angels', 'Michael Shaara', None, 'html,lrf'],
 33: ['Band Of Brothers', 'Stephen E Ambrose', None, 'lrf,txt'],
 34: ['The Gates of Rome', 'Conn Iggulden', None, 'lrf,rar'],
 35: ['The Death of Kings', 'Conn Iggulden', 'Bantam Dell', 'lit,lrf'],
 36: ['The Field of Swords', 'Conn Iggulden', None, 'lrf,rar'],
 37: ['Masterman Ready', 'Marryat, Captain Frederick', None, 'lrf'],
 38: ['With the Lightnings',
      'David Drake',
      'Baen Publishing Enterprises',
      'lit,lrf'],
 39: ['Lt. Leary, Commanding',
      'David Drake',
      'Baen Publishing Enterprises',
      'lit,lrf'],
 40: ['The Far Side of The Stars',
      'David Drake',
      'Baen Publishing Enterprises',
      'lrf,rar'],
 41: ['The Way to Glory',
      'David Drake',
      'Baen Publishing Enterprises',
      'lrf,rar'],
 42: ['Some Golden Harbor', 'David Drake', 'Baen Books', 'lrf,rar'],
 43: ['Harry Potter And The Half-Blood Prince',
      'J. K. Rowling',
      None,
      'lrf,rar'],
 44: ['Harry Potter and the Order of the Phoenix',
      'J. K. Rowling',
      None,
      'lrf,rtf'],
 45: ['The Stars at War', 'David Weber , Steve White', None, 'lrf,rtf'],
 46: ['The Stars at War II',
      'Steve White',
      'Baen Publishing Enterprises',
      'lrf,rar'],
 47: ['Exodus', 'Steve White,Shirley Meier', 'Baen Books', 'lrf,rar'],
 48: ['Harry Potter and the Goblet of Fire',
      'J. K. Rowling',
      None,
      'lrf,rar'],
 49: ['Harry Potter and the Prisoner of Azkaban',
      'J. K. Rowling',
      None,
      'lrf,rtf'],
 50: ['Harry Potter and the Chamber of Secrets',
      'J. K. Rowling',
      None,
      'lit,lrf'],
 51: ['Harry Potter and the Deathly Hallows',
      'J.K. Rowling',
      None,
      'lit,lrf,pdf'],
 52: ["His Majesty's Dragon", 'Naomi Novik', None, 'lrf,rar'],
 53: ['Throne of Jade', 'Naomi Novik', 'Del Rey', 'lit,lrf'],
 54: ['Black Powder War', 'Naomi Novik', 'Del Rey', 'lrf,rar'],
 55: ['War and Peace', 'Leo Tolstoy', 'gutenberg.org', 'lrf,txt'],
 56: ['Anna Karenina', 'Leo Tolstoy', 'gutenberg.org', 'lrf,txt'],
 57: ['A Shorter History of Rome',
      'Eugene Lawrence,Sir William Smith',
      'gutenberg.org',
      'lrf,zip'],
 58: ['The Name of the Rose', 'Umberto Eco', None, 'lrf,rar'],
 71: ["Wind Rider's Oath", 'David Weber', 'Baen', 'lrf'],
 74: ['Rally Cry', 'William R Forstchen', None, 'htm,lrf'],
 86: ['Empire of Ivory', 'Naomi Novik', None, 'lrf,rar'],
 87: ["Renegade's Magic", 'Robin Hobb', None, 'lrf,rar'],
 89: ['Master and commander',
      "Patrick O'Brian",
      'Fontana,\n1971',
      'lit,lrf'],
 91: ['A Companion to Wolves',
      'Sarah Monette,Elizabeth Beär',
      None,
      'lrf,rar'],
 92: ['The Lions of al-Rassan', 'Guy Gavriel Kay', 'Eos', 'lit,lrf'],
 93: ['Gardens of the Moon', 'Steven Erikson', 'Tor Fantasy', 'lit,lrf'],
 95: ['The Master and Margarita',
      'Mikhail Bulgakov',
      'N.Y. : Knopf, 1992.',
      'lrf,rtf'],
 120: ['Deadhouse Gates',
       'Steven Erikson',
       'London : Bantam Books, 2001.',
       'lit,lrf'],
 121: ['Memories of Ice', 'Steven Erikson', 'Bantam Books', 'lit,lrf'],
 123: ['House of Chains', 'Steven Erikson', 'Bantam Books', 'lit,lrf'],
 125: ['Midnight Tides', 'Steven Erikson', 'Bantam Books', 'lit,lrf'],
 126: ['The Bonehunters', 'Steven Erikson', 'Bantam Press', 'lit,lrf'],
 129: ['Guns, germs, and steel: the fates of human societies',
       'Jared Diamond',
       'New York : W.W. Norton, c1997.',
       'lit,lrf'],
 136: ['Wildcards', 'George R. R. Martin', None, 'html,lrf'],
 138: ['Off Armageddon Reef', 'David Weber', 'Tor Books', 'lit,lrf'],
 144: ['Atonement',
       'Ian McEwan',
       'New York : Nan A. Talese/Doubleday, 2002.',
       'lrf,rar'],
 146: ['1632', 'Eric Flint', 'Baen Books', 'lit,lrf'],
 147: ['1633', 'David Weber,Eric Flint,Dru Blair', 'Baen', 'lit,lrf'],
 148: ['1634: The Baltic War',
       'David Weber,Eric Flint',
       'Baen',
       'lit,lrf'],
 150: ['The Dragonbone Chair', 'Tad Williams', 'DAW Trade', 'lrf,rtf'],
 152: ['The Little Book That Beats the Market',
       'Joel Greenblatt',
       'Wiley',
       'epub,lrf'],
 153: ['Pride of Carthage', 'David Anthony Durham', 'Anchor', 'lit,lrf'],
 154: ['Stone of farewell',
       'Tad Williams',
       'New York : DAW Books, 1990.',
       'lrf,txt'],
 166: ['American Gods', 'Neil Gaiman', 'HarperTorch', 'lit,lrf'],
 176: ['Pillars of the Earth',
       'Ken Follett',
       'New American Library',
       'lit,lrf'],
 182: ['The Eye of the world',
       'Robert Jordan',
       'New York : T. Doherty Associates, c1990.',
       'lit,lrf'],
 188: ['The Great Hunt', 'Robert Jordan', 'ATOM', 'lrf,zip'],
 189: ['The Dragon Reborn', 'Robert Jordan', None, 'lit,lrf'],
 190: ['The Shadow Rising', 'Robert Jordan', None, 'lit,lrf'],
 191: ['The Fires of Heaven',
       'Robert Jordan',
       'Time Warner Books Uk',
       'lit,lrf'],
 216: ['Lord of chaos',
       'Robert Jordan',
       'New York : TOR, c1994.',
       'lit,lrf'],
 217: ['A Crown of Swords', 'Robert Jordan', None, 'lit,lrf'],
 236: ['The Path of Daggers', 'Robert Jordan', None, 'lit,lrf'],
 238: ['The Client',
       'John Grisham',
       'New York : Island, 1994, c1993.',
       'lit,lrf'],
 240: ["Winter's Heart", 'Robert Jordan', None, 'lit,lrf'],
 242: ['In the Beginning was the Command Line',
       'Neal Stephenson',
       None,
       'lrf,txt'],
 249: ['Crossroads of Twilight', 'Robert Jordan', None, 'lit,lrf'],
 251: ['Caves of Steel', 'Isaac Asimov', 'Del Rey', 'lrf,zip'],
 253: ["Hunter's Run",
       'George R. R. Martin,Gardner Dozois,Daniel Abraham',
       'Eos',
       'lrf,rar'],
 257: ['Knife of Dreams', 'Robert Jordan', None, 'lit,lrf'],
 258: ['Saturday',
       'Ian McEwan',
       'London : Jonathan Cape, 2005.',
       'lrf,txt'],
 259: ['My name is Red',
       'Orhan Pamuk; translated from the Turkish by Erda\u011f G\xf6knar',
       'New York : Alfred A. Knopf, 2001.',
       'lit,lrf'],
 265: ['Harbinger', 'David Mack', 'Star Trek', 'lit,lrf'],
 267: ['Summon the Thunder',
       'Dayton Ward,Kevin Dilmore',
       'Pocket Books',
       'lit,lrf'],
 268: ['Shalimar the Clown',
       'Salman Rushdie',
       'New York : Random House, 2005.',
       'lit,lrf'],
 269: ['Reap the Whirlwind', 'David Mack', 'Star Trek', 'lit,lrf'],
 272: ['Mistborn', 'Brandon Sanderson', 'Tor Fantasy', 'lrf,rar'],
 273: ['The Thousandfold Thought',
       'R. Scott Bakker',
       'Overlook TP',
       'lrf,rtf'],
 276: ['Elantris',
       'Brandon Sanderson',
       'New York : Tor, 2005.',
       'lrf,rar'],
 291: ['Sundiver',
       'David Brin',
       'New York : Bantam Books, 1995.',
       'lit,lrf'],
 299: ['Imperium', 'Robert Harris', 'Arrow', 'lrf,rar'],
 300: ['Startide Rising', 'David Brin', 'Bantam', 'htm,lrf'],
 301: ['The Uplift War', 'David Brin', 'Spectra', 'lit,lrf'],
 304: ['Brightness Reef', 'David Brin', 'Orbit', 'lrf,rar'],
 305: ["Infinity's Shore", 'David Brin', 'Spectra', 'txt'],
 306: ["Heaven's Reach", 'David Brin', 'Spectra', 'lrf,rar'],
 325: ["Foundation's Triumph", 'David Brin', 'Easton Press', 'lit,lrf'],
 327: ['I am Charlotte Simmons', 'Tom Wolfe', 'Vintage', 'htm,lrf'],
 335: ['The Currents of Space', 'Isaac Asimov', None, 'lit,lrf'],
 340: ['The Other Boleyn Girl',
       'Philippa Gregory',
       'Touchstone',
       'lit,lrf'],
 341: ["Old Man's War", 'John Scalzi', 'Tor', 'htm,lrf'],
 342: ['The Ghost Brigades',
       'John Scalzi',
       'Tor Science Fiction',
       'html,lrf'],
 343: ['The Last Colony', 'John S"calzi', 'Tor Books', 'html,lrf'],
 344: ['Gossip Girl', 'Cecily von Ziegesar', 'Warner Books', 'lrf,rtf'],
 347: ['Little Brother', 'Cory Doctorow', 'Tor Teen', 'lrf'],
 348: ['The Reality Dysfunction',
       'Peter F. Hamilton',
       'Pan MacMillan',
       'lit,lrf'],
 353: ['A Thousand Splendid Suns',
       'Khaled Hosseini',
       'Center Point Large Print',
       'lit,lrf'],
 354: ['Amsterdam', 'Ian McEwan', 'Anchor', 'lrf,txt'],
 355: ['The Neutronium Alchemist',
       'Peter F. Hamilton',
       'Aspect',
       'lit,lrf'],
 356: ['The Naked God', 'Peter F. Hamilton', 'Aspect', 'lit,lrf'],
 421: ['A Shadow in Summer', 'Daniel Abraham', 'Tor Fantasy', 'lrf,rar'],
 427: ['Lonesome Dove', 'Larry M\\cMurtry', None, 'lit,lrf'],
 440: ['Ghost', 'John Ringo', 'Baen', 'lit,lrf'],
 441: ['Kildar', 'John Ringo', 'Baen', 'lit,lrf'],
 443: ['Hidden Empire ', 'Kevin J. Anderson', 'Aspect', 'lrf,rar'],
 444: ['The Gun Seller',
       'Hugh Laurie',
       'Washington Square Press',
       'lrf,rar']
 }

    tests = {
             'Dysfunction' : {348},
             'title:Dysfunction' : {348},
             'Title:Dysfunction' : {348},
             'title:Dysfunction OR author:Laurie': {348, 444},
             '(tag:txt or tag:pdf)': {33, 258, 354, 305, 242, 51, 55, 56, 154},
             '(tag:txt OR tag:pdf) and author:Tolstoy': {55, 56},
             'Tolstoy txt': {55, 56},
             'Hamilton Amsterdam' : set(),
             'Beär' : {91},
             'dysfunc or tolstoy': {348, 55, 56},
             'tag:txt AND NOT tolstoy': {33, 258, 354, 305, 242, 154},
             'not tag:lrf' : {305},
             'london:thames': {13},
             'publisher:london:thames': {13},
             '"(1977)"': {13},
             'jack weatherford orc': {30},
             'S\\"calzi': {343},
             'author:S\\"calzi': {343},
             '"S\\"calzi"': {343},
             'M\\\\cMurtry': {427},
             'author:Tolstoy (tag:txt OR tag:pdf)': {55, 56},
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
            return set()
        query = query.lower()
        if candidates:
            return {key for key, val in self.texts.items()
                if key in candidates and query and query
                        in getattr(getter(val), 'lower', lambda : '')()}
        else:
            return {key for key, val in self.texts.items()
                if query and query in getattr(getter(val), 'lower', lambda : '')()}

    def run_tests(self, ae):
        for query in self.tests.keys():
            res = self.parse(query)
            ae(self.tests[query], res, f'Failed for query: {query}')


class TestSQP(unittest.TestCase):

    def do_test(self, optimize=False):
        tester = Tester(['authors', 'author', 'series', 'formats', 'format',
            'publisher', 'rating', 'tags', 'tag', 'comments', 'comment', 'cover',
            'isbn', 'ondevice', 'pubdate', 'size', 'date', 'title', '#read',
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
        # docstring tests
        t(r'"""a\1b"""', 'W', r'a\1b')
        t(r'("""a\1b""" AND """c""" OR d)',
          'O', '(', 'W', r'a\1b', 'W', 'AND', 'W', 'c',  'W', 'OR', 'W', 'd', 'O', ')')
        t(r'template:="""a\1b"""', 'W', r'template:=a\1b')
        t('template:="""a\nb"""', 'W', 'template:=a\nb')
        t(r'template:"""=a\1b"""', 'W', r'template:=a\1b')
        t(r'template:"""program: return ("\"1\"")#@#n:1"""', 'W',
          r'template:program: return ("\"1\"")#@#n:1')


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSQP)


class TestRunner(unittest.main):

    def createTests(self):
        self.test = find_tests()


def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)


if __name__ == '__main__':
    run()
