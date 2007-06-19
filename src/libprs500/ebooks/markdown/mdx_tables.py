#!/usr/bin/env python

"""
Table extension for Python-Markdown
"""

import markdown


class TablePattern(markdown.Pattern) :
	def __init__ (self, md):
		markdown.Pattern.__init__(self, r'^\|([^\n]*)\|(\n|$)')
		self.md = md

	def handleMatch(self, m, doc) :
		# a single line represents a row
		tr = doc.createElement('tr')
		tr.appendChild(doc.createTextNode('\n'))
		# chunks between pipes represent cells
		for t in m.group(2).split('|'):
			if len(t) >= 2 and t.startswith('*') and t.endswith('*'):
				# if a cell is bounded by asterisks, it is a <th>
				td = doc.createElement('th')
				t = t[1:-1]
			else:
				# otherwise it is a <td>
				td = doc.createElement('td')
			# apply inline patterns on chunks
			for n in self.md._handleInline(t):
				if(type(n) == unicode):
					td.appendChild(doc.createTextNode(n))
				else:
					td.appendChild(n)
			tr.appendChild(td)
			# very long lines are evil
			tr.appendChild(doc.createTextNode('\n'))
		return tr


class TablePostprocessor:
	def run(self, doc):
		# markdown wrapped our <tr>s in a <p>, we fix that here
		def test_for_p(element):
			return element.type == 'element' and element.nodeName == 'p'
		# replace "p > tr" with "table > tr"
		for element in doc.find(test_for_p):
			for node in element.childNodes:
				if(node.type == 'text' and node.value.strip() == ''):
					# skip leading whitespace
					continue
				if (node.type == 'element' and node.nodeName == 'tr'):
					element.nodeName = 'table'
				break


class TableExtension(markdown.Extension):
	def extendMarkdown(self, md, md_globals):
		md.inlinePatterns.insert(0, TablePattern(md))
		md.postprocessors.append(TablePostprocessor())


def makeExtension(configs):
	return TableExtension(configs)


