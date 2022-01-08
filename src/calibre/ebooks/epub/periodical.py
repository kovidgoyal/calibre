#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from uuid import uuid4
import time

from calibre.constants import __appname__, __version__
from calibre import strftime, prepare_string_for_xml as xml
from calibre.utils.date import parse_date

SONY_METADATA = '''\
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:prs="http://xmlns.sony.net/e-book/prs/">
    <rdf:Description rdf:about="">
        <dc:title>{title}</dc:title>
        <dc:publisher>{publisher}</dc:publisher>
        <dcterms:alternative>{short_title}</dcterms:alternative>
        <dcterms:issued>{issue_date}</dcterms:issued>
        <dc:language>{language}</dc:language>
        <dcterms:conformsTo rdf:resource="http://xmlns.sony.net/e-book/prs/periodicals/1.0/newspaper/1.0"/>
        <dcterms:type rdf:resource="http://xmlns.sony.net/e-book/prs/datatype/newspaper"/>
        <dcterms:type rdf:resource="http://xmlns.sony.net/e-book/prs/datatype/periodical"/>
    </rdf:Description>
</rdf:RDF>
'''

SONY_ATOM = '''\
<?xml version="1.0" encoding="utf-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:prs="http://xmlns.sony.net/e-book/prs/"
    xmlns:media="http://video.search.yahoo.com/mrss"
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

<title>{short_title}</title>
<updated>{updated}</updated>
<id>{id}</id>
{entries}
</feed>
'''

SONY_ATOM_SECTION = '''\
<entry rdf:ID="{title}">
  <title>{title}</title>
  <link href="{href}"/>
  <id>{id}</id>
  <updated>{updated}</updated>
  <summary>{desc}</summary>
  <category term="{short_title}/{title}"
      scheme="http://xmlns.sony.net/e-book/terms/" label="{title}"/>
  <dc:type xsi:type="prs:datatype">newspaper/section</dc:type>
  <dcterms:isReferencedBy rdf:resource=""/>
</entry>
'''

SONY_ATOM_ENTRY = '''\
<entry>
  <title>{title}</title>
  <author><name>{author}</name></author>
  <link href="{href}"/>
  <id>{id}</id>
  <updated>{updated}</updated>
  <summary>{desc}</summary>
  <category term="{short_title}/{section_title}"
      scheme="http://xmlns.sony.net/e-book/terms/" label="{section_title}"/>
  <dcterms:extent xsi:type="prs:word-count">{word_count}</dcterms:extent>
  <dc:type xsi:type="prs:datatype">newspaper/article</dc:type>
  <dcterms:isReferencedBy rdf:resource="#{section_title}"/>
</entry>
'''


def sony_metadata(oeb):
    m = oeb.metadata
    title = short_title = str(m.title[0])
    publisher = __appname__ + ' ' + __version__
    try:
        pt = str(oeb.metadata.publication_type[0])
        short_title = ':'.join(pt.split(':')[2:])
    except:
        pass

    try:
        date = parse_date(str(m.date[0]),
                as_utc=False).strftime('%Y-%m-%d')
    except:
        date = strftime('%Y-%m-%d')
    try:
        language = str(m.language[0]).replace('_', '-')
    except:
        language = 'en'
    short_title = xml(short_title, True)

    metadata = SONY_METADATA.format(title=xml(title),
            short_title=short_title,
            publisher=xml(publisher), issue_date=xml(date),
            language=xml(language))

    updated = strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    def cal_id(x):
        for k, v in x.attrib.items():
            if k.endswith('scheme') and v == 'uuid':
                return True

    try:
        base_id = str(list(filter(cal_id, m.identifier))[0])
    except:
        base_id = str(uuid4())

    toc = oeb.toc

    if False and toc.depth() < 3:
        # Single section periodical
        # Disabled since I prefer the current behavior
        from calibre.ebooks.oeb.base import TOC
        section = TOC(klass='section', title=_('All articles'),
                    href=oeb.spine[2].href)
        for x in toc:
            section.nodes.append(x)
        toc = TOC(klass='periodical', href=oeb.spine[2].href,
                    title=str(oeb.metadata.title[0]))
        toc.nodes.append(section)

    entries = []
    seen_titles = set()
    for i, section in enumerate(toc):
        if not section.href:
            continue
        secid = 'section%d'%i
        sectitle = section.title
        if not sectitle:
            sectitle = _('Unknown')
        d = 1
        bsectitle = sectitle
        while sectitle in seen_titles:
            sectitle = bsectitle + ' ' + str(d)
            d += 1
        seen_titles.add(sectitle)
        sectitle = xml(sectitle, True)
        secdesc = section.description
        if not secdesc:
            secdesc = ''
        secdesc = xml(secdesc)
        entries.append(SONY_ATOM_SECTION.format(title=sectitle,
            href=section.href, id=xml(base_id)+'/'+secid,
            short_title=short_title, desc=secdesc, updated=updated))

        for j, article in enumerate(section):
            if not article.href:
                continue
            atitle = article.title
            btitle = atitle
            d = 1
            while atitle in seen_titles:
                atitle = btitle + ' ' + str(d)
                d += 1

            auth = article.author if article.author else ''
            desc = section.description
            if not desc:
                desc = ''
            aid = 'article%d'%j

            entries.append(SONY_ATOM_ENTRY.format(
                title=xml(atitle),
                author=xml(auth),
                updated=updated,
                desc=desc,
                short_title=short_title,
                section_title=sectitle,
                href=article.href,
                word_count=str(1),
                id=xml(base_id)+'/'+secid+'/'+aid
            ))

    atom = SONY_ATOM.format(short_title=short_title,
            entries='\n\n'.join(entries), updated=updated,
            id=xml(base_id)).encode('utf-8')

    return metadata, atom
