// For questions about the portuguese hyphenation patterns
// ask Lailson Bandeira (lailsonbm at gmail dot com)
// based on LaTeX patterns in Portuguese, by Pedro J. de Rezende and J.Joao Dias Almeida (http://www.ctan.org/tex-archive/language/hyph-utf8/tex/generic/hyph-utf8/patterns/)
Hyphenator.languages['pt'] = {
	leftmin : 2,
	rightmin : 4,
	shortestPattern : 1,
	longestPattern : 3,
	specialChars : "áéíóúãõàçâêô",
	patterns : {
		2 : "1-",
		3 : "1ba1be1bi1bo1bu1bá1bâ1bã1bé1bí1bó1bú1bê1bõ1ca1ce1ci1co1cu1cá1câ1cã1cé1cí1có1cú1cê1cõ1ça1çe1çi1ço1çu1çá1çâ1çã1çé1çí1çó1çú1çê1çõ1da1de1di1do1du1dá1dâ1dã1dé1dí1dó1dú1dê1dõ1fa1fe1fi1fo1fu1fá1fâ1fã1fé1fí1fó1fú1fê1fõ1ga1ge1gi1go1gu1gá1gâ1gã1gé1gí1gó1gú1gê1gõ1ja1je1ji1jo1ju1já1jâ1jã1jé1jí1jó1jú1jê1jõ1ka1ke1ki1ko1ku1ká1kâ1kã1ké1kí1kó1kú1kê1kõ1la1le1li1lo1lu1lá1lâ1lã1lé1lí1ló1lú1lê1lõ1ma1me1mi1mo1mu1má1mâ1mã1mé1mí1mó1mú1mê1mõ1na1ne1ni1no1nu1ná1nâ1nã1né1ní1nó1nú1nê1nõ1pa1pe1pi1po1pu1pá1pâ1pã1pé1pí1pó1pú1pê1põ1ra1re1ri1ro1ru1rá1râ1rã1ré1rí1ró1rú1rê1rõ1sa1se1si1so1su1sá1sâ1sã1sé1sí1só1sú1sê1sõ1ta1te1ti1to1tu1tá1tâ1tã1té1tí1tó1tú1tê1tõ1va1ve1vi1vo1vu1vá1vâ1vã1vé1ví1vó1vú1vê1võ1xa1xe1xi1xo1xu1xá1xâ1xã1xé1xí1xó1xú1xê1xõ1za1ze1zi1zo1zu1zá1zâ1zã1zé1zí1zó1zú1zê1zõa3aa3ea3oc3ce3ae3ee3oi3ai3ei3ii3oi3âi3êi3ôo3ao3eo3or3rs3su3au3eu3ou3u",
		4 : "1b2l1b2r1c2h1c2l1c2r1d2l1d2r1f2l1f2r1g2l1g2r1k2l1k2r1l2h1n2h1p2l1p2r1t2l1t2r1v2l1v2r1w2l1w2r",
		5 : "1gu4a1gu4e1gu4i1gu4o1qu4a1qu4e1qu4i1qu4o"
	}
};