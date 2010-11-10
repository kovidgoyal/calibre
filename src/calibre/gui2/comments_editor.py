#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from lxml import html
from lxml.html import soupparser

from PyQt4.Qt import QApplication, QFontInfo, QPalette, QSize, QWidget, \
    QToolBar, QVBoxLayout, QAction, QIcon
from PyQt4.QtWebKit import QWebView

from calibre.ebooks.chardet import xml_to_unicode
from calibre import xml_replace_entities

class EditorWidget(QWebView):

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)

        for name, icon, text, checkable in [
                ('bold', 'format-text-bold', _('Bold'), True),
                ('italic', 'format-text-italic', _('Italic'), True),
                ('underline', 'format-text-underline', _('Underline'), True),
                ('strikethrough', 'format-text-underline', _('Underline'), True),
            ]:
            ac = QAction(QIcon(I(icon+'.png')), text, self)
            ac.setCheckable(checkable)
            setattr(self, 'action_'+name, ac)

    def sizeHint(self):
        return QSize(150, 150)

    @dynamic_property
    def html(self):

        def fget(self):
            ans = u''
            try:
                raw = unicode(self.page().mainFrame().toHtml())
                raw = xml_to_unicode(raw, strip_encoding_pats=True,
                                    resolve_entities=True)[0]

                try:
                    root = html.fromstring(raw)
                except:
                    root = soupparser.fromstring(raw)

                elems = []
                for body in root.xpath('//body'):
                    elems += [html.tostring(x, encoding=unicode) for x in body if
                        x.tag != 'script']
                if len(elems) > 1:
                    ans = u'<div>%s</div>'%(u''.join(elems))
                else:
                    ans = u''.join(elems)
                ans = xml_replace_entities(ans)
            except:
                import traceback
                traceback.print_exc()

            return ans

        def fset(self, val):
            self.setHtml(val)
            f = QFontInfo(QApplication.font(self)).pixelSize()
            b = unicode(QApplication.palette().color(QPalette.Normal,
                            QPalette.Base).name())
            c = unicode(QApplication.palette().color(QPalette.Normal,
                            QPalette.Text).name())
            style = 'font-size: %dpx; background-color: %s; color: %s' % (f, b,
                    c)

            for body in self.page().mainFrame().documentElement().findAll('body'):
                body.setAttribute('style', style)
            self.page().setContentEditable(True)

        return property(fget=fget, fset=fset)


class Editor(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.toolbar = QToolBar(self)
        self.editor = EditorWidget(self)
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self.toolbar)
        self._layout.addWidget(self.editor)

    @dynamic_property
    def html(self):
        def fset(self, v):
            self.editor.html = v
        return property(fget=lambda self:self.editor.html, fset=fset)



if __name__ == '__main__':
    app = QApplication([])
    w = Editor()
    w.resize(800, 600)
    w.show()
# testing {{{

    w.html = '''
<div>

 <h3>From Publishers Weekly</h3>
 <div>
 Starred Review. Paul Dirac (1902–1984) shared the Nobel Prize for physics with Erwin Schrödinger in 1933, but whereas physicists regard Dirac as one of the giants of the 20th century, he isn't as well known outside the profession. This may be due to the lack of humorous quips attributed to Dirac, as compared with an Einstein or a Feynman. If he spoke at all, it was with one-word answers that made Calvin Coolidge look loquacious . Dirac adhered to Keats's admonition that Beauty is truth, truth beauty: if an equation was beautiful, it was probably correct, and vice versa. His most famous equation predicted the positron (now used in PET scans), which is the antiparticle of the electron, and antimatter in general. In 1955, Dirac came up with a primitive version of string theory, which today is the rock star branch of physics. Physicist Farmelo (<i>It Must Be Beautiful</i>) speculates that Dirac suffered from undiagnosed autism because his character quirks resembled autism's symptoms. Farmelo proves himself a wizard at explaining the arcane aspects of particle physics. His great affection for his odd but brilliant subject shows on every page, giving Dirac the biography any great scientist deserves. <i>(Sept.)</i> <br>Copyright © Reed Business Information, a division of Reed Elsevier Inc. All rights reserved.

 </div>
 <h3>Review</h3>
 <div>
 <div><b><i>Kirkus</i> *Starred Review*</b><br> “Paul Dirac was a giant of 20th-century physics, and this rich, satisfying biography does him justice…. [A] nuanced portrayal of an introverted eccentric who held his own in a small clique of revolutionary scientific geniuses.”<br><p><b>Peter Higgs, <i>Times (UK)</i></b><br> “Fascinating reading… Graham Farmelo has done a splendid job of portraying Dirac and his world. The biography is a major achievement.”</p> <p><b><i>Telegraph</i></b><br> “If Newton was the Shakespeare of British physics, Dirac was its Milton, the most fascinating and enigmatic of all our great scientists. And he now has a biography to match his talents: a wonderful book by Graham Farmelo. The story it tells is moving, sometimes comic, sometimes infinitely sad, and goes to the roots of what we mean by truth in science.”</p> <p><b><i>New Statesman</i></b><br> “A marvelously rich and intimate study.”</p> <p><b><i>Sunday Herald</i></b><br> “Farmelo’s splendid biography has enough scientific exposition for the biggest science fan and enough human interest for the rest of us. It creates a picture of a man who was a great theoretical scientist but also an awkward but oddly endearing human being…. This is a fine book: a fitting tribute to a significant and intriguing scientific figure.”</p> <p><b><i>The Economist</i></b><br> “[A] sympathetic portrait….Of the small group of young men who developed quantum mechanics and revolutionized physics almost a century ago, he truly stands out. Paul Dirac was a strange man in a strange world. This biography, long overdue, is most welcome.”</p> <p><b><i>Times Higher Education Supplement (UK)</i></b><br> “A page-turner about Dirac and quantum physics seems a contradiction in terms, but Graham Farmelo's new book, <i>The Strangest Man</i>, is an eminently readable account of the developments in physics throughout the 1920s, 1930s and 1940s and the life of one of the discipline's key scientists.”</p> <p><b><i>New Scientist</i></b><br> “Enthralling… Regardless of whether Dirac was autistic or simply unpleasant, he is an icon of modern thought and Farmelo's book gives us a genuine insight into his life and times.”</p> <p><b>John Gribbin, <i>Literary Review</i></b><br> “Fascinating …[A] suberb book.”</p> <p><b>Tom Stoppard</b><br> “In the group portrait of genius in 20th century physics, Paul Dirac is the stick figure. Who was he, and what did he do? For all non-physicists who have followed the greatest intellectual adventure of modern times, this is the missing book.”</p> <p><b>Michael Frayn</b><br> “Graham Farmelo has found the subject he was born to write about, and brought it off triumphantly. Dirac was one of the great founding fathers of modern physics, a theoretician who explored the sub-atomic world through the power of pure mathematics. He was also a most extraordinary man - an extreme introvert, and perhaps autistic. Farmelo traces the outward events as authoritatively as the inward. His book is a monumental achievement – one of the great scientific biographies.”</p> <p><b>Roger Highfield, Editor,<i>New Scientist</i></b><br> “A must-read for anyone interested in the extraordinary power of pure thought. With this revelatory, moving and definitive biography, Graham Farmelo provides the first real glimpse inside the bizarre mind of Paul Dirac.”</p> <p><b>Martin Rees, President of the Royal Society, Master of Trinity College, Professor of Cosmology and Astrophysics at the University of Cambridge and Astronomer Royal</b><br> “Paul Dirac, though a quiet and withdrawn character, made towering contributions to the greatest scientific revolution of the 20th century. In this sensitive and meticulously researched biography, Graham Farmelo does Dirac proud, and offers a wonderful insight into the European academic environment in which his creativity flourished."</p> <p><b><i>Barnes &amp; Noble Review</i></b><br> “Farmelo explains all the science relevant to understanding Dirac, and does it well; equally good is his careful and copious account of a personal life that was dogged by a sense of tragedy…. [I]f [Dirac] could read Farmelo’s absorbing and accessible account of his life he would see that it had magic in it, and triumph: the magic of revelations about the deep nature of reality, and the triumph of having moved human understanding several steps further towards the light.”</p> <p><b><i>Newark Star-Ledger</i></b><br> “[An] excellently researched biography…. [T]his book is a major step toward making a staggeringly brilliant, remote man seem likeable.”</p> <p><b><i>Los Angeles Times</i></b><br> “Graham Farmelo has managed to haul Dirac onstage in an affectionate and meticulously researched book that illuminates both his era and his science…. Farmelo is very good at portraying this locked-in, asocial creature, often with an eerie use of the future-perfect tense…, which has the virtue of putting the reader in the same room with people who are long gone.”</p> <p><b>SeedMagazine.com</b><br> “[A] tour de force filled with insight and revelation. <i>The Strangest Man</i> offers an unprecedented and gripping view of Dirac not only as a scientist, but also as a human being.”</p> <p><b><i>New York Times Book Review</i></b><br> “This biography is a gift. It is both wonderfully written (certainly not a given in the category Accessible Biographies of Mathematical Physicists) and a thought-provoking meditation on human achievement, limitations and the relations between the two…. [T]he most satisfying and memorable biography I have read in years.”</p> <p><b><i>Time Magazine</i></b><br> “Paul Dirac won a Nobel Prize for Physics at 31. He was one of quantum mechanics’ founding fathers, an Einstein-level genius. He was also virtually incapable of having normal social interactions. Graham Farmelo’s biography explains Dirac’s mysterious life and work.”<br><br><b><i>Library Journal</i></b><br> “Farmelo did not pick the easiest biography to write – its subject lived a largely solitary life in deep thought. But Dirac was also beset with tragedy… and in that respect, the author proposes some novel insights into what shaped the man. This would be a strong addition to a bibliography of magnificent 20th-century physicist biographies, including Walter Issacson’s Einstein, Kai Bird and Martin J. Sherwin’s <i>American Prometheus: The Triumph and Tragedy of J. Robert Oppenheimer</i>, and James Gleick’s <i>Genius: The Life and Science of Richard Feynman</i>.”<br><br><b><i>American Journal of Physics</i></b><br> “[A] very moving biography…. It would have been easy to simply fill the biography with Dirac stories of which there is a cornucopia, many of which are actually true. But Farmelo does much more than that. He has met and spoken with people who knew Dirac including the surviving members of his family. He has been to where Dirac lived and worked and he understands the physics. What has emerged is a 558 page biography, which is a model of the genre. Dirac was so private and emotionally self-contained that one wonders if anyone really knew him. Farmelo’s book is as close as we are likely to come."<br><br><b><i>American Scientist</i></b><br> “[A] highly readable and sympathetic biography of the taciturn British physicist who can be said, with little exaggeration, to have invented modern theoretical physics. The book is a real achievement, alternately gripping and illuminating.”<br><br><b><i>Natural History</i></b><br> “Farmelo’s eloquent and empathetic examination of Dirac’s life raises this book above the level of workmanlike popularization. Using personal interviews, scientific archives, and newly released documents and letters, he’s managed – as much as anyone could – to dispel the impression of the physicist as a real-life Mr. Spock, the half Vulcan of Star Trek.”<br><br><b><i>Science</i></b><br> “[A] consummate and seamless biography…. Farmelo has succeeded masterfully in the difficult genre of writing a great scientist’s life for a general audience.”<br><br><b><i>Physics Today</i></b><br> “[An] excellent biography of a hero of physics…. [I]n <i>The Strangest Man</i>, we are treated to a fascinating, thoroughly researched, and well-written account of one of the most important figures of modern physics.”<br><br><b><i>Nature</i></b><br> “As this excellent biography by Graham Farmelo shows, Dirac’s contributions to science were profound and far-ranging; modern ideas that have their origins in quantum electrodynamics are inspired by his insight…. The effortless writing style shows that it is possible to describe profound ideas without compromising scientific integrity or readability."<br><br><b>Freeman Dyson, <i>New York Review of Books</i></b><br> “In Farmelo’s book we see Dirac as a character in a human drama, carrying his full share of tragedy as well as triumph.”<b><i><br></i></b> <br><b><i>American Journal of Physics</i></b><br> “Farmelo’s exhaustively researched biography…not only traces the life of its title figure but portrays the unfolding of quantum mechanics with cinematic scope…. He repeatedly zooms his storyteller’s lens in and out between intimate close-ups and grand scenes, all the while attempting to make the physics comprehensible to the general readership without trivializing it. In his telling, the front-line scientists are a competitive troupe of explorers, jockeying for renown – only the uncharted territory is in the mind and the map is mathematical…. We read works like Farmelo’s for enlightenment, for inspiration, and for the reminder that science is a quintessentially human endeavor, with all...</p></div>

 </div>
</div>
<div>

 <h3>From Publishers Weekly</h3>
 <div>
 Starred Review. Paul Dirac (1902–1984) shared the Nobel Prize for physics with Erwin Schrödinger in 1933, but whereas physicists regard Dirac as one of the giants of the 20th century, he isn't as well known outside the profession. This may be due to the lack of humorous quips attributed to Dirac, as compared with an Einstein or a Feynman. If he spoke at all, it was with one-word answers that made Calvin Coolidge look loquacious . Dirac adhered to Keats's admonition that Beauty is truth, truth beauty: if an equation was beautiful, it was probably correct, and vice versa. His most famous equation predicted the positron (now used in PET scans), which is the antiparticle of the electron, and antimatter in general. In 1955, Dirac came up with a primitive version of string theory, which today is the rock star branch of physics. Physicist Farmelo (<i>It Must Be Beautiful</i>) speculates that Dirac suffered from undiagnosed autism because his character quirks resembled autism's symptoms. Farmelo proves himself a wizard at explaining the arcane aspects of particle physics. His great affection for his odd but brilliant subject shows on every page, giving Dirac the biography any great scientist deserves. <i>(Sept.)</i> <br>Copyright © Reed Business Information, a division of Reed Elsevier Inc. All rights reserved.

 </div>
 <h3>Review</h3>
 <div>
 <div><b><i>Kirkus</i> *Starred Review*</b><br> “Paul Dirac was a giant of 20th-century physics, and this rich, satisfying biography does him justice…. [A] nuanced portrayal of an introverted eccentric who held his own in a small clique of revolutionary scientific geniuses.”<br><p><b>Peter Higgs, <i>Times (UK)</i></b><br> “Fascinating reading… Graham Farmelo has done a splendid job of portraying Dirac and his world. The biography is a major achievement.”</p> <p><b><i>Telegraph</i></b><br> “If Newton was the Shakespeare of British physics, Dirac was its Milton, the most fascinating and enigmatic of all our great scientists. And he now has a biography to match his talents: a wonderful book by Graham Farmelo. The story it tells is moving, sometimes comic, sometimes infinitely sad, and goes to the roots of what we mean by truth in science.”</p> <p><b><i>New Statesman</i></b><br> “A marvelously rich and intimate study.”</p> <p><b><i>Sunday Herald</i></b><br> “Farmelo’s splendid biography has enough scientific exposition for the biggest science fan and enough human interest for the rest of us. It creates a picture of a man who was a great theoretical scientist but also an awkward but oddly endearing human being…. This is a fine book: a fitting tribute to a significant and intriguing scientific figure.”</p> <p><b><i>The Economist</i></b><br> “[A] sympathetic portrait….Of the small group of young men who developed quantum mechanics and revolutionized physics almost a century ago, he truly stands out. Paul Dirac was a strange man in a strange world. This biography, long overdue, is most welcome.”</p> <p><b><i>Times Higher Education Supplement (UK)</i></b><br> “A page-turner about Dirac and quantum physics seems a contradiction in terms, but Graham Farmelo's new book, <i>The Strangest Man</i>, is an eminently readable account of the developments in physics throughout the 1920s, 1930s and 1940s and the life of one of the discipline's key scientists.”</p> <p><b><i>New Scientist</i></b><br> “Enthralling… Regardless of whether Dirac was autistic or simply unpleasant, he is an icon of modern thought and Farmelo's book gives us a genuine insight into his life and times.”</p> <p><b>John Gribbin, <i>Literary Review</i></b><br> “Fascinating …[A] suberb book.”</p> <p><b>Tom Stoppard</b><br> “In the group portrait of genius in 20th century physics, Paul Dirac is the stick figure. Who was he, and what did he do? For all non-physicists who have followed the greatest intellectual adventure of modern times, this is the missing book.”</p> <p><b>Michael Frayn</b><br> “Graham Farmelo has found the subject he was born to write about, and brought it off triumphantly. Dirac was one of the great founding fathers of modern physics, a theoretician who explored the sub-atomic world through the power of pure mathematics. He was also a most extraordinary man - an extreme introvert, and perhaps autistic. Farmelo traces the outward events as authoritatively as the inward. His book is a monumental achievement – one of the great scientific biographies.”</p> <p><b>Roger Highfield, Editor,<i>New Scientist</i></b><br> “A must-read for anyone interested in the extraordinary power of pure thought. With this revelatory, moving and definitive biography, Graham Farmelo provides the first real glimpse inside the bizarre mind of Paul Dirac.”</p> <p><b>Martin Rees, President of the Royal Society, Master of Trinity College, Professor of Cosmology and Astrophysics at the University of Cambridge and Astronomer Royal</b><br> “Paul Dirac, though a quiet and withdrawn character, made towering contributions to the greatest scientific revolution of the 20th century. In this sensitive and meticulously researched biography, Graham Farmelo does Dirac proud, and offers a wonderful insight into the European academic environment in which his creativity flourished."</p> <p><b><i>Barnes &amp; Noble Review</i></b><br> “Farmelo explains all the science relevant to understanding Dirac, and does it well; equally good is his careful and copious account of a personal life that was dogged by a sense of tragedy…. [I]f [Dirac] could read Farmelo’s absorbing and accessible account of his life he would see that it had magic in it, and triumph: the magic of revelations about the deep nature of reality, and the triumph of having moved human understanding several steps further towards the light.”</p> <p><b><i>Newark Star-Ledger</i></b><br> “[An] excellently researched biography…. [T]his book is a major step toward making a staggeringly brilliant, remote man seem likeable.”</p> <p><b><i>Los Angeles Times</i></b><br> “Graham Farmelo has managed to haul Dirac onstage in an affectionate and meticulously researched book that illuminates both his era and his science…. Farmelo is very good at portraying this locked-in, asocial creature, often with an eerie use of the future-perfect tense…, which has the virtue of putting the reader in the same room with people who are long gone.”</p> <p><b>SeedMagazine.com</b><br> “[A] tour de force filled with insight and revelation. <i>The Strangest Man</i> offers an unprecedented and gripping view of Dirac not only as a scientist, but also as a human being.”</p> <p><b><i>New York Times Book Review</i></b><br> “This biography is a gift. It is both wonderfully written (certainly not a given in the category Accessible Biographies of Mathematical Physicists) and a thought-provoking meditation on human achievement, limitations and the relations between the two…. [T]he most satisfying and memorable biography I have read in years.”</p> <p><b><i>Time Magazine</i></b><br> “Paul Dirac won a Nobel Prize for Physics at 31. He was one of quantum mechanics’ founding fathers, an Einstein-level genius. He was also virtually incapable of having normal social interactions. Graham Farmelo’s biography explains Dirac’s mysterious life and work.”<br><br><b><i>Library Journal</i></b><br> “Farmelo did not pick the easiest biography to write – its subject lived a largely solitary life in deep thought. But Dirac was also beset with tragedy… and in that respect, the author proposes some novel insights into what shaped the man. This would be a strong addition to a bibliography of magnificent 20th-century physicist biographies, including Walter Issacson’s Einstein, Kai Bird and Martin J. Sherwin’s <i>American Prometheus: The Triumph and Tragedy of J. Robert Oppenheimer</i>, and James Gleick’s <i>Genius: The Life and Science of Richard Feynman</i>.”<br><br><b><i>American Journal of Physics</i></b><br> “[A] very moving biography…. It would have been easy to simply fill the biography with Dirac stories of which there is a cornucopia, many of which are actually true. But Farmelo does much more than that. He has met and spoken with people who knew Dirac including the surviving members of his family. He has been to where Dirac lived and worked and he understands the physics. What has emerged is a 558 page biography, which is a model of the genre. Dirac was so private and emotionally self-contained that one wonders if anyone really knew him. Farmelo’s book is as close as we are likely to come."<br><br><b><i>American Scientist</i></b><br> “[A] highly readable and sympathetic biography of the taciturn British physicist who can be said, with little exaggeration, to have invented modern theoretical physics. The book is a real achievement, alternately gripping and illuminating.”<br><br><b><i>Natural History</i></b><br> “Farmelo’s eloquent and empathetic examination of Dirac’s life raises this book above the level of workmanlike popularization. Using personal interviews, scientific archives, and newly released documents and letters, he’s managed – as much as anyone could – to dispel the impression of the physicist as a real-life Mr. Spock, the half Vulcan of Star Trek.”<br><br><b><i>Science</i></b><br> “[A] consummate and seamless biography…. Farmelo has succeeded masterfully in the difficult genre of writing a great scientist’s life for a general audience.”<br><br><b><i>Physics Today</i></b><br> “[An] excellent biography of a hero of physics…. [I]n <i>The Strangest Man</i>, we are treated to a fascinating, thoroughly researched, and well-written account of one of the most important figures of modern physics.”<br><br><b><i>Nature</i></b><br> “As this excellent biography by Graham Farmelo shows, Dirac’s contributions to science were profound and far-ranging; modern ideas that have their origins in quantum electrodynamics are inspired by his insight…. The effortless writing style shows that it is possible to describe profound ideas without compromising scientific integrity or readability."<br><br><b>Freeman Dyson, <i>New York Review of Books</i></b><br> “In Farmelo’s book we see Dirac as a character in a human drama, carrying his full share of tragedy as well as triumph.”<b><i><br></i></b> <br><b><i>American Journal of Physics</i></b><br> “Farmelo’s exhaustively researched biography…not only traces the life of its title figure but portrays the unfolding of quantum mechanics with cinematic scope…. He repeatedly zooms his storyteller’s lens in and out between intimate close-ups and grand scenes, all the while attempting to make the physics comprehensible to the general readership without trivializing it. In his telling, the front-line scientists are a competitive troupe of explorers, jockeying for renown – only the uncharted territory is in the mind and the map is mathematical…. We read works like Farmelo’s for enlightenment, for inspiration, and for the reminder that science is a quintessentially human endeavor, with all...</p></div>

 </div>
</div>
    '''.decode('utf-8')
    app.exec_()
    #print w.html.encode('utf-8')

# }}}
    #print w.html
