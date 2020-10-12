#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest, sys, argparse

from lxml import etree, html

from css_selectors.errors import SelectorSyntaxError, ExpressionError
from css_selectors.parser import tokenize, parse
from css_selectors.select import Select


class TestCSSSelectors(unittest.TestCase):

    # Test data {{{
    HTML_IDS = '''
<html id="html"><head>
  <link id="link-href" href="foo" />
  <link id="link-nohref" />
</head><body>
<div id="outer-div">
 <a id="name-anchor" name="foo"></a>
 <a id="tag-anchor" rel="tag" href="http://localhost/foo">link</a>
 <a id="nofollow-anchor" rel="nofollow" href="https://example.org">
    link</a>
 <ol id="first-ol" class="a b c">
   <li id="first-li">content</li>
   <li id="second-li" lang="En-us">
     <div id="li-div">
     </div>
   </li>
   <li id="third-li" class="ab c"></li>
   <li id="fourth-li" class="ab
c"></li>
   <li id="fifth-li"></li>
   <li id="sixth-li"></li>
   <li id="seventh-li">  </li>
 </ol>
 <p id="paragraph">
   <b id="p-b">hi</b> <em id="p-em">there</em>
   <b id="p-b2">guy</b>
   <input type="checkbox" id="checkbox-unchecked" />
   <input type="checkbox" id="checkbox-disabled" disabled="" />
   <input type="text" id="text-checked" checked="checked" />
   <input type="hidden" />
   <input type="hidden" disabled="disabled" />
   <input type="checkbox" id="checkbox-checked" checked="checked" />
   <input type="checkbox" id="checkbox-disabled-checked"
          disabled="disabled" checked="checked" />
   <fieldset id="fieldset" disabled="disabled">
     <input type="checkbox" id="checkbox-fieldset-disabled" />
     <input type="hidden" />
   </fieldset>
 </p>
 <ol id="second-ol">
 </ol>
 <map name="dummymap">
   <area shape="circle" coords="200,250,25" href="foo.html" id="area-href" />
   <area shape="default" id="area-nohref" />
 </map>
</div>
<div id="foobar-div" foobar="ab bc
cde"><span id="foobar-span"></span></div>
</body></html>
'''
    HTML_SHAKESPEARE = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" debug="true">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
</head>
<body>
<div id="test">
<div class="dialog">
<h2>As You Like It</h2>
<div id="playwright">
by William Shakespeare
</div>
<div class="dialog scene thirdClass" id="scene1">
<h3>ACT I, SCENE III. A room in the palace.</h3>
<div class="dialog">
<div class="direction">Enter CELIA and ROSALIND</div>
</div>
<div id="speech1" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.1">Why, cousin! why, Rosalind! Cupid have mercy! not a word?</div>
</div>
<div id="speech2" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.2">Not one to throw at a dog.</div>
</div>
<div id="speech3" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.3">No, thy words are too precious to be cast away upon</div>
<div id="scene1.3.4">curs; throw some of them at me; come, lame me with reasons.</div>
</div>
<div id="speech4" class="character">ROSALIND</div>
<div id="speech5" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.8">But is all this for your father?</div>
</div>
<div class="dialog">
<div id="scene1.3.5">Then there were two cousins laid up; when the one</div>
<div id="scene1.3.6">should be lamed with reasons and the other mad</div>
<div id="scene1.3.7">without any.</div>
</div>
<div id="speech6" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.9">No, some of it is for my child's father. O, how</div>
<div id="scene1.3.10">full of briers is this working-day world!</div>
</div>
<div id="speech7" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.11">They are but burs, cousin, thrown upon thee in</div>
<div id="scene1.3.12">holiday foolery: if we walk not in the trodden</div>
<div id="scene1.3.13">paths our very petticoats will catch them.</div>
</div>
<div id="speech8" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.14">I could shake them off my coat: these burs are in my heart.</div>
</div>
<div id="speech9" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.15">Hem them away.</div>
</div>
<div id="speech10" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.16">I would try, if I could cry 'hem' and have him.</div>
</div>
<div id="speech11" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.17">Come, come, wrestle with thy affections.</div>
</div>
<div id="speech12" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.18">O, they take the part of a better wrestler than myself!</div>
</div>
<div id="speech13" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.19">O, a good wish upon you! you will try in time, in</div>
<div id="scene1.3.20">despite of a fall. But, turning these jests out of</div>
<div id="scene1.3.21">service, let us talk in good earnest: is it</div>
<div id="scene1.3.22">possible, on such a sudden, you should fall into so</div>
<div id="scene1.3.23">strong a liking with old Sir Rowland's youngest son?</div>
</div>
<div id="speech14" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.24">The duke my father loved his father dearly.</div>
</div>
<div id="speech15" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.25">Doth it therefore ensue that you should love his son</div>
<div id="scene1.3.26">dearly? By this kind of chase, I should hate him,</div>
<div id="scene1.3.27">for my father hated his father dearly; yet I hate</div>
<div id="scene1.3.28">not Orlando.</div>
</div>
<div id="speech16" class="character">ROSALIND</div>
<div title="wtf" class="dialog">
<div id="scene1.3.29">No, faith, hate him not, for my sake.</div>
</div>
<div id="speech17" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.30">Why should I not? doth he not deserve well?</div>
</div>
<div id="speech18" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.31">Let me love him for that, and do you love him</div>
<div id="scene1.3.32">because I do. Look, here comes the duke.</div>
</div>
<div id="speech19" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.33">With his eyes full of anger.</div>
<div class="direction">Enter DUKE FREDERICK, with Lords</div>
</div>
<div id="speech20" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.34">Mistress, dispatch you with your safest haste</div>
<div id="scene1.3.35">And get you from our court.</div>
</div>
<div id="speech21" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.36">Me, uncle?</div>
</div>
<div id="speech22" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.37">You, cousin</div>
<div id="scene1.3.38">Within these ten days if that thou be'st found</div>
<div id="scene1.3.39">So near our public court as twenty miles,</div>
<div id="scene1.3.40">Thou diest for it.</div>
</div>
<div id="speech23" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.41">                  I do beseech your grace,</div>
<div id="scene1.3.42">Let me the knowledge of my fault bear with me:</div>
<div id="scene1.3.43">If with myself I hold intelligence</div>
<div id="scene1.3.44">Or have acquaintance with mine own desires,</div>
<div id="scene1.3.45">If that I do not dream or be not frantic,--</div>
<div id="scene1.3.46">As I do trust I am not--then, dear uncle,</div>
<div id="scene1.3.47">Never so much as in a thought unborn</div>
<div id="scene1.3.48">Did I offend your highness.</div>
</div>
<div id="speech24" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.49">Thus do all traitors:</div>
<div id="scene1.3.50">If their purgation did consist in words,</div>
<div id="scene1.3.51">They are as innocent as grace itself:</div>
<div id="scene1.3.52">Let it suffice thee that I trust thee not.</div>
</div>
<div id="speech25" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.53">Yet your mistrust cannot make me a traitor:</div>
<div id="scene1.3.54">Tell me whereon the likelihood depends.</div>
</div>
<div id="speech26" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.55">Thou art thy father's daughter; there's enough.</div>
</div>
<div id="speech27" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.56">So was I when your highness took his dukedom;</div>
<div id="scene1.3.57">So was I when your highness banish'd him:</div>
<div id="scene1.3.58">Treason is not inherited, my lord;</div>
<div id="scene1.3.59">Or, if we did derive it from our friends,</div>
<div id="scene1.3.60">What's that to me? my father was no traitor:</div>
<div id="scene1.3.61">Then, good my liege, mistake me not so much</div>
<div id="scene1.3.62">To think my poverty is treacherous.</div>
</div>
<div id="speech28" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.63">Dear sovereign, hear me speak.</div>
</div>
<div id="speech29" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.64">Ay, Celia; we stay'd her for your sake,</div>
<div id="scene1.3.65">Else had she with her father ranged along.</div>
</div>
<div id="speech30" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.66">I did not then entreat to have her stay;</div>
<div id="scene1.3.67">It was your pleasure and your own remorse:</div>
<div id="scene1.3.68">I was too young that time to value her;</div>
<div id="scene1.3.69">But now I know her: if she be a traitor,</div>
<div id="scene1.3.70">Why so am I; we still have slept together,</div>
<div id="scene1.3.71">Rose at an instant, learn'd, play'd, eat together,</div>
<div id="scene1.3.72">And wheresoever we went, like Juno's swans,</div>
<div id="scene1.3.73">Still we went coupled and inseparable.</div>
</div>
<div id="speech31" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.74">She is too subtle for thee; and her smoothness,</div>
<div id="scene1.3.75">Her very silence and her patience</div>
<div id="scene1.3.76">Speak to the people, and they pity her.</div>
<div id="scene1.3.77">Thou art a fool: she robs thee of thy name;</div>
<div id="scene1.3.78">And thou wilt show more bright and seem more virtuous</div>
<div id="scene1.3.79">When she is gone. Then open not thy lips:</div>
<div id="scene1.3.80">Firm and irrevocable is my doom</div>
<div id="scene1.3.81">Which I have pass'd upon her; she is banish'd.</div>
</div>
<div id="speech32" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.82">Pronounce that sentence then on me, my liege:</div>
<div id="scene1.3.83">I cannot live out of her company.</div>
</div>
<div id="speech33" class="character">DUKE FREDERICK</div>
<div class="dialog">
<div id="scene1.3.84">You are a fool. You, niece, provide yourself:</div>
<div id="scene1.3.85">If you outstay the time, upon mine honour,</div>
<div id="scene1.3.86">And in the greatness of my word, you die.</div>
<div class="direction">Exeunt DUKE FREDERICK and Lords</div>
</div>
<div id="speech34" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.87">O my poor Rosalind, whither wilt thou go?</div>
<div id="scene1.3.88">Wilt thou change fathers? I will give thee mine.</div>
<div id="scene1.3.89">I charge thee, be not thou more grieved than I am.</div>
</div>
<div id="speech35" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.90">I have more cause.</div>
</div>
<div id="speech36" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.91">                  Thou hast not, cousin;</div>
<div id="scene1.3.92">Prithee be cheerful: know'st thou not, the duke</div>
<div id="scene1.3.93">Hath banish'd me, his daughter?</div>
</div>
<div id="speech37" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.94">That he hath not.</div>
</div>
<div id="speech38" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.95">No, hath not? Rosalind lacks then the love</div>
<div id="scene1.3.96">Which teacheth thee that thou and I am one:</div>
<div id="scene1.3.97">Shall we be sunder'd? shall we part, sweet girl?</div>
<div id="scene1.3.98">No: let my father seek another heir.</div>
<div id="scene1.3.99">Therefore devise with me how we may fly,</div>
<div id="scene1.3.100">Whither to go and what to bear with us;</div>
<div id="scene1.3.101">And do not seek to take your change upon you,</div>
<div id="scene1.3.102">To bear your griefs yourself and leave me out;</div>
<div id="scene1.3.103">For, by this heaven, now at our sorrows pale,</div>
<div id="scene1.3.104">Say what thou canst, I'll go along with thee.</div>
</div>
<div id="speech39" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.105">Why, whither shall we go?</div>
</div>
<div id="speech40" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.106">To seek my uncle in the forest of Arden.</div>
</div>
<div id="speech41" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.107">Alas, what danger will it be to us,</div>
<div id="scene1.3.108">Maids as we are, to travel forth so far!</div>
<div id="scene1.3.109">Beauty provoketh thieves sooner than gold.</div>
</div>
<div id="speech42" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.110">I'll put myself in poor and mean attire</div>
<div id="scene1.3.111">And with a kind of umber smirch my face;</div>
<div id="scene1.3.112">The like do you: so shall we pass along</div>
<div id="scene1.3.113">And never stir assailants.</div>
</div>
<div id="speech43" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.114">Were it not better,</div>
<div id="scene1.3.115">Because that I am more than common tall,</div>
<div id="scene1.3.116">That I did suit me all points like a man?</div>
<div id="scene1.3.117">A gallant curtle-axe upon my thigh,</div>
<div id="scene1.3.118">A boar-spear in my hand; and--in my heart</div>
<div id="scene1.3.119">Lie there what hidden woman's fear there will--</div>
<div id="scene1.3.120">We'll have a swashing and a martial outside,</div>
<div id="scene1.3.121">As many other mannish cowards have</div>
<div id="scene1.3.122">That do outface it with their semblances.</div>
</div>
<div id="speech44" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.123">What shall I call thee when thou art a man?</div>
</div>
<div id="speech45" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.124">I'll have no worse a name than Jove's own page;</div>
<div id="scene1.3.125">And therefore look you call me Ganymede.</div>
<div id="scene1.3.126">But what will you be call'd?</div>
</div>
<div id="speech46" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.127">Something that hath a reference to my state</div>
<div id="scene1.3.128">No longer Celia, but Aliena.</div>
</div>
<div id="speech47" class="character">ROSALIND</div>
<div class="dialog">
<div id="scene1.3.129">But, cousin, what if we assay'd to steal</div>
<div id="scene1.3.130">The clownish fool out of your father's court?</div>
<div id="scene1.3.131">Would he not be a comfort to our travel?</div>
</div>
<div id="speech48" class="character">CELIA</div>
<div class="dialog">
<div id="scene1.3.132">He'll go along o'er the wide world with me;</div>
<div id="scene1.3.133">Leave me alone to woo him. Let's away,</div>
<div id="scene1.3.134">And get our jewels and our wealth together,</div>
<div id="scene1.3.135">Devise the fittest time and safest way</div>
<div id="scene1.3.136">To hide us from pursuit that will be made</div>
<div id="scene1.3.137">After my flight. Now go we in content</div>
<div id="scene1.3.138">To liberty and not to banishment.</div>
<div class="direction">Exeunt</div>
</div>
</div>
</div>
</div>
</body>
</html>
'''


# }}}

    ae = unittest.TestCase.assertEqual

    def test_tokenizer(self):  # {{{
        tokens = [
            type('')(item) for item in tokenize(
                r'E\ é > f [a~="y\"x"]:nth(/* fu /]* */-3.7)')]
        self.ae(tokens, [
            "<IDENT 'E é' at 0>",
            "<S ' ' at 4>",
            "<DELIM '>' at 5>",
            "<S ' ' at 6>",
            # the no-break space is not whitespace in CSS
            "<IDENT 'f ' at 7>",  # f\xa0
            "<DELIM '[' at 9>",
            "<IDENT 'a' at 10>",
            "<DELIM '~' at 11>",
            "<DELIM '=' at 12>",
            "<STRING 'y\"x' at 13>",
            "<DELIM ']' at 19>",
            "<DELIM ':' at 20>",
            "<IDENT 'nth' at 21>",
            "<DELIM '(' at 24>",
            "<NUMBER '-3.7' at 37>",
            "<DELIM ')' at 41>",
            "<EOF at 42>",
        ])
    # }}}

    def test_parser(self):  # {{{
        def repr_parse(css):
            selectors = parse(css)
            for selector in selectors:
                assert selector.pseudo_element is None
            return [repr(selector.parsed_tree).replace("(u'", "('")
                    for selector in selectors]

        def parse_many(first, *others):
            result = repr_parse(first)
            for other in others:
                assert repr_parse(other) == result
            return result

        assert parse_many('*') == ['Element[*]']
        assert parse_many('*|*') == ['Element[*]']
        assert parse_many('*|foo') == ['Element[foo]']
        assert parse_many('foo|*') == ['Element[foo|*]']
        assert parse_many('foo|bar') == ['Element[foo|bar]']
        # This will never match, but it is valid:
        assert parse_many('#foo#bar') == ['Hash[Hash[Element[*]#foo]#bar]']
        assert parse_many(
            'div>.foo',
            'div> .foo',
            'div >.foo',
            'div > .foo',
            'div \n>  \t \t .foo', 'div\r>\n\n\n.foo', 'div\f>\f.foo'
        ) == ['CombinedSelector[Element[div] > Class[Element[*].foo]]']
        assert parse_many('td.foo,.bar',
            'td.foo, .bar',
            'td.foo\t\r\n\f ,\t\r\n\f .bar'
        ) == [
            'Class[Element[td].foo]',
            'Class[Element[*].bar]'
        ]
        assert parse_many('div, td.foo, div.bar span') == [
            'Element[div]',
            'Class[Element[td].foo]',
            'CombinedSelector[Class[Element[div].bar] '
            '<followed> Element[span]]']
        assert parse_many('div > p') == [
            'CombinedSelector[Element[div] > Element[p]]']
        assert parse_many('td:first') == [
            'Pseudo[Element[td]:first]']
        assert parse_many('td:first') == [
            'Pseudo[Element[td]:first]']
        assert parse_many('td :first') == [
            'CombinedSelector[Element[td] '
            '<followed> Pseudo[Element[*]:first]]']
        assert parse_many('td :first') == [
            'CombinedSelector[Element[td] '
            '<followed> Pseudo[Element[*]:first]]']
        assert parse_many('a[name]', 'a[ name\t]') == [
            'Attrib[Element[a][name]]']
        assert parse_many('a [name]') == [
            'CombinedSelector[Element[a] <followed> Attrib[Element[*][name]]]']
        self.ae(parse_many('a[rel="include"]', 'a[rel = include]'), [
            "Attrib[Element[a][rel = 'include']]"])
        assert parse_many("a[hreflang |= 'en']", "a[hreflang|=en]") == [
            "Attrib[Element[a][hreflang |= 'en']]"]
        self.ae(parse_many('div:nth-child(10)'), [
            "Function[Element[div]:nth-child(['10'])]"])
        assert parse_many(':nth-child(2n+2)') == [
            "Function[Element[*]:nth-child(['2', 'n', '+2'])]"]
        assert parse_many('div:nth-of-type(10)') == [
            "Function[Element[div]:nth-of-type(['10'])]"]
        assert parse_many('div div:nth-of-type(10) .aclass') == [
            'CombinedSelector[CombinedSelector[Element[div] <followed> '
            "Function[Element[div]:nth-of-type(['10'])]] "
            '<followed> Class[Element[*].aclass]]']
        assert parse_many('label:only') == [
            'Pseudo[Element[label]:only]']
        assert parse_many('a:lang(fr)') == [
            "Function[Element[a]:lang(['fr'])]"]
        assert parse_many('div:contains("foo")') == [
            "Function[Element[div]:contains(['foo'])]"]
        assert parse_many('div#foobar') == [
            'Hash[Element[div]#foobar]']
        assert parse_many('div:not(div.foo)') == [
            'Negation[Element[div]:not(Class[Element[div].foo])]']
        assert parse_many('td ~ th') == [
            'CombinedSelector[Element[td] ~ Element[th]]']
    # }}}

    def test_pseudo_elements(self):  # {{{
        def parse_pseudo(css):
            result = []
            for selector in parse(css):
                pseudo = selector.pseudo_element
                pseudo = type('')(pseudo) if pseudo else pseudo
                # No Symbol here
                assert pseudo is None or isinstance(pseudo, type(''))
                selector = repr(selector.parsed_tree).replace("(u'", "('")
                result.append((selector, pseudo))
            return result

        def parse_one(css):
            result = parse_pseudo(css)
            assert len(result) == 1
            return result[0]

        self.ae(parse_one('foo'), ('Element[foo]', None))
        self.ae(parse_one('*'), ('Element[*]', None))
        self.ae(parse_one(':empty'), ('Pseudo[Element[*]:empty]', None))

        # Special cases for CSS 2.1 pseudo-elements
        self.ae(parse_one(':BEfore'), ('Element[*]', 'before'))
        self.ae(parse_one(':aftER'), ('Element[*]', 'after'))
        self.ae(parse_one(':First-Line'), ('Element[*]', 'first-line'))
        self.ae(parse_one(':First-Letter'), ('Element[*]', 'first-letter'))

        self.ae(parse_one('::befoRE'), ('Element[*]', 'before'))
        self.ae(parse_one('::AFter'), ('Element[*]', 'after'))
        self.ae(parse_one('::firsT-linE'), ('Element[*]', 'first-line'))
        self.ae(parse_one('::firsT-letteR'), ('Element[*]', 'first-letter'))

        self.ae(parse_one('::text-content'), ('Element[*]', 'text-content'))
        self.ae(parse_one('::attr(name)'), (
            "Element[*]", "FunctionalPseudoElement[::attr(['name'])]"))

        self.ae(parse_one('::Selection'), ('Element[*]', 'selection'))
        self.ae(parse_one('foo:after'), ('Element[foo]', 'after'))
        self.ae(parse_one('foo::selection'), ('Element[foo]', 'selection'))
        self.ae(parse_one('lorem#ipsum ~ a#b.c[href]:empty::selection'), (
            'CombinedSelector[Hash[Element[lorem]#ipsum] ~ '
            'Pseudo[Attrib[Class[Hash[Element[a]#b].c][href]]:empty]]',
            'selection'))

        parse_pseudo('foo:before, bar, baz:after') == [
            ('Element[foo]', 'before'),
            ('Element[bar]', None),
            ('Element[baz]', 'after')]
    # }}}

    def test_specificity(self):  # {{{
        def specificity(css):
            selectors = parse(css)
            assert len(selectors) == 1
            return selectors[0].specificity()

        assert specificity('*') == (0, 0, 0)
        assert specificity(' foo') == (0, 0, 1)
        assert specificity(':empty ') == (0, 1, 0)
        assert specificity(':before') == (0, 0, 1)
        assert specificity('*:before') == (0, 0, 1)
        assert specificity(':nth-child(2)') == (0, 1, 0)
        assert specificity('.bar') == (0, 1, 0)
        assert specificity('[baz]') == (0, 1, 0)
        assert specificity('[baz="4"]') == (0, 1, 0)
        assert specificity('[baz^="4"]') == (0, 1, 0)
        assert specificity('#lipsum') == (1, 0, 0)

        assert specificity(':not(*)') == (0, 0, 0)
        assert specificity(':not(foo)') == (0, 0, 1)
        assert specificity(':not(.foo)') == (0, 1, 0)
        assert specificity(':not([foo])') == (0, 1, 0)
        assert specificity(':not(:empty)') == (0, 1, 0)
        assert specificity(':not(#foo)') == (1, 0, 0)

        assert specificity('foo:empty') == (0, 1, 1)
        assert specificity('foo:before') == (0, 0, 2)
        assert specificity('foo::before') == (0, 0, 2)
        assert specificity('foo:empty::before') == (0, 1, 2)

        assert specificity('#lorem + foo#ipsum:first-child > bar:first-line'
            ) == (2, 1, 3)
    # }}}

    def test_parse_errors(self):  # {{{
        def get_error(css):
            try:
                parse(css)
            except SelectorSyntaxError:
                # Py2, Py3, ...
                return str(sys.exc_info()[1]).replace("(u'", "('")

        self.ae(get_error('attributes(href)/html/body/a'), (
            "Expected selector, got <DELIM '(' at 10>"))
        assert get_error('attributes(href)') == (
            "Expected selector, got <DELIM '(' at 10>")
        assert get_error('html/body/a') == (
            "Expected selector, got <DELIM '/' at 4>")
        assert get_error(' ') == (
            "Expected selector, got <EOF at 1>")
        assert get_error('div, ') == (
            "Expected selector, got <EOF at 5>")
        assert get_error(' , div') == (
            "Expected selector, got <DELIM ',' at 1>")
        assert get_error('p, , div') == (
            "Expected selector, got <DELIM ',' at 3>")
        assert get_error('div > ') == (
            "Expected selector, got <EOF at 6>")
        assert get_error('  > div') == (
            "Expected selector, got <DELIM '>' at 2>")
        assert get_error('foo|#bar') == (
            "Expected ident or '*', got <HASH 'bar' at 4>")
        assert get_error('#.foo') == (
            "Expected selector, got <DELIM '#' at 0>")
        assert get_error('.#foo') == (
            "Expected ident, got <HASH 'foo' at 1>")
        assert get_error(':#foo') == (
            "Expected ident, got <HASH 'foo' at 1>")
        assert get_error('[*]') == (
            "Expected '|', got <DELIM ']' at 2>")
        assert get_error('[foo|]') == (
            "Expected ident, got <DELIM ']' at 5>")
        assert get_error('[#]') == (
            "Expected ident or '*', got <DELIM '#' at 1>")
        assert get_error('[foo=#]') == (
            "Expected string or ident, got <DELIM '#' at 5>")
        assert get_error('[href]a') == (
            "Expected selector, got <IDENT 'a' at 6>")
        assert get_error('[rel=stylesheet]') is None
        assert get_error('[rel:stylesheet]') == (
            "Operator expected, got <DELIM ':' at 4>")
        assert get_error('[rel=stylesheet') == (
            "Expected ']', got <EOF at 15>")
        assert get_error(':lang(fr)') is None
        assert get_error(':lang(fr') == (
            "Expected an argument, got <EOF at 8>")
        assert get_error(':contains("foo') == (
            "Unclosed string at 10")
        assert get_error('foo!') == (
            "Expected selector, got <DELIM '!' at 3>")

        # Mis-placed pseudo-elements
        assert get_error('a:before:empty') == (
            "Got pseudo-element ::before not at the end of a selector")
        assert get_error('li:before a') == (
            "Got pseudo-element ::before not at the end of a selector")
        assert get_error(':not(:before)') == (
            "Got pseudo-element ::before inside :not() at 12")
        assert get_error(':not(:not(a))') == (
            "Got nested :not()")
    # }}}

    def test_select(self):  # {{{
        document = etree.fromstring(self.HTML_IDS, parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
        select = Select(document)

        def select_ids(selector):
            for elem in select(selector):
                yield elem.get('id')

        def pcss(main, *selectors, **kwargs):
            result = list(select_ids(main))
            for selector in selectors:
                self.ae(list(select_ids(selector)), result)
            return result
        all_ids = pcss('*')
        self.ae(all_ids[:6], [
            'html', None, 'link-href', 'link-nohref', None, 'outer-div'])
        self.ae(all_ids[-1:], ['foobar-span'])
        self.ae(pcss('div'), ['outer-div', 'li-div', 'foobar-div'])
        self.ae(pcss('DIV'), [
            'outer-div', 'li-div', 'foobar-div'])  # case-insensitive in HTML
        self.ae(pcss('div div'), ['li-div'])
        self.ae(pcss('div, div div'), ['outer-div', 'li-div', 'foobar-div'])
        self.ae(pcss('a[name]'), ['name-anchor'])
        self.ae(pcss('a[NAme]'), ['name-anchor'])  # case-insensitive in HTML:
        self.ae(pcss('a[rel]'), ['tag-anchor', 'nofollow-anchor'])
        self.ae(pcss('a[rel="tag"]'), ['tag-anchor'])
        self.ae(pcss('a[href*="localhost"]'), ['tag-anchor'])
        self.ae(pcss('a[href*=""]'), [])
        self.ae(pcss('a[href^="http"]'), ['tag-anchor', 'nofollow-anchor'])
        self.ae(pcss('a[href^="http:"]'), ['tag-anchor'])
        self.ae(pcss('a[href^=""]'), [])
        self.ae(pcss('a[href$="org"]'), ['nofollow-anchor'])
        self.ae(pcss('a[href$=""]'), [])
        self.ae(pcss('div[foobar~="bc"]', 'div[foobar~="cde"]', skip_webkit=True), ['foobar-div'])
        self.ae(pcss('[foobar~="ab bc"]', '[foobar~=""]', '[foobar~=" \t"]'), [])
        self.ae(pcss('div[foobar~="cd"]'), [])
        self.ae(pcss('*[lang|="En"]', '[lang|="En-us"]'), ['second-li'])
        # Attribute values are case sensitive
        self.ae(pcss('*[lang|="en"]', '[lang|="en-US"]', skip_webkit=True), [])
        self.ae(pcss('*[lang|="e"]'), [])
        self.ae(pcss(':lang("EN")', '*:lang(en-US)', skip_webkit=True), ['second-li', 'li-div'])
        self.ae(pcss(':lang("e")'), [])
        self.ae(pcss('li:nth-child(1)', 'li:first-child'), ['first-li'])
        self.ae(pcss('li:nth-child(3)', '#first-li ~ :nth-child(3)'), ['third-li'])
        self.ae(pcss('li:nth-child(10)'), [])
        self.ae(pcss('li:nth-child(2n)', 'li:nth-child(even)', 'li:nth-child(2n+0)'), ['second-li', 'fourth-li', 'sixth-li'])
        self.ae(pcss('li:nth-child(+2n+1)', 'li:nth-child(odd)'), ['first-li', 'third-li', 'fifth-li', 'seventh-li'])
        self.ae(pcss('li:nth-child(2n+4)'), ['fourth-li', 'sixth-li'])
        self.ae(pcss('li:nth-child(3n+1)'), ['first-li', 'fourth-li', 'seventh-li'])
        self.ae(pcss('li:nth-last-child(0)'), [])
        self.ae(pcss('li:nth-last-child(1)', 'li:last-child'), ['seventh-li'])
        self.ae(pcss('li:nth-last-child(2n)', 'li:nth-last-child(even)'), ['second-li', 'fourth-li', 'sixth-li'])
        self.ae(pcss('li:nth-last-child(2n+2)'), ['second-li', 'fourth-li', 'sixth-li'])
        self.ae(pcss('ol:first-of-type'), ['first-ol'])
        self.ae(pcss('ol:nth-child(1)'), [])
        self.ae(pcss('ol:nth-of-type(2)'), ['second-ol'])
        self.ae(pcss('ol:nth-last-of-type(1)'), ['second-ol'])
        self.ae(pcss('span:only-child'), ['foobar-span'])
        self.ae(pcss('li div:only-child'), ['li-div'])
        self.ae(pcss('div *:only-child'), ['li-div', 'foobar-span'])
        self.ae(pcss('p *:only-of-type', skip_webkit=True), ['p-em', 'fieldset'])
        self.ae(pcss('p:only-of-type', skip_webkit=True), ['paragraph'])
        self.ae(pcss('a:empty', 'a:EMpty'), ['name-anchor'])
        self.ae(pcss('li:empty'), ['third-li', 'fourth-li', 'fifth-li', 'sixth-li'])
        self.ae(pcss(':root', 'html:root', 'li:root'), ['html'])
        self.ae(pcss('* :root', 'p *:root'), [])
        self.ae(pcss('.a', '.b', '*.a', 'ol.a'), ['first-ol'])
        self.ae(pcss('.c', '*.c'), ['first-ol', 'third-li', 'fourth-li'])
        self.ae(pcss('ol *.c', 'ol li.c', 'li ~ li.c', 'ol > li.c'), [
            'third-li', 'fourth-li'])
        self.ae(pcss('#first-li', 'li#first-li', '*#first-li'), ['first-li'])
        self.ae(pcss('li div', 'li > div', 'div div'), ['li-div'])
        self.ae(pcss('div > div'), [])
        self.ae(pcss('div>.c', 'div > .c'), ['first-ol'])
        self.ae(pcss('div + div'), ['foobar-div'])
        self.ae(pcss('a ~ a'), ['tag-anchor', 'nofollow-anchor'])
        self.ae(pcss('a[rel="tag"] ~ a'), ['nofollow-anchor'])
        self.ae(pcss('ol#first-ol li:last-child'), ['seventh-li'])
        self.ae(pcss('ol#first-ol *:last-child'), ['li-div', 'seventh-li'])
        self.ae(pcss('#outer-div:first-child'), ['outer-div'])
        self.ae(pcss('#outer-div :first-child'), [
            'name-anchor', 'first-li', 'li-div', 'p-b',
            'checkbox-fieldset-disabled', 'area-href'])
        self.ae(pcss('a[href]'), ['tag-anchor', 'nofollow-anchor'])
        self.ae(pcss(':not(*)'), [])
        self.ae(pcss('a:not([href])'), ['name-anchor'])
        self.ae(pcss('ol :Not(li[class])', skip_webkit=True), [
            'first-li', 'second-li', 'li-div',
            'fifth-li', 'sixth-li', 'seventh-li'])
        self.ae(pcss(r'di\a0 v', r'div\['), [])
        self.ae(pcss(r'[h\a0 ref]', r'[h\]ref]'), [])

        self.assertRaises(ExpressionError, lambda : tuple(select('body:nth-child')))

        select = Select(document, ignore_inappropriate_pseudo_classes=True)
        self.assertGreater(len(tuple(select('p:hover'))), 0)

    def test_select_shakespeare(self):
        document = html.document_fromstring(self.HTML_SHAKESPEARE)
        select = Select(document)
        count = lambda s: sum(1 for r in select(s))

        # Data borrowed from http://mootools.net/slickspeed/

        # Changed from original; probably because I'm only
        self.ae(count('*'), 249)
        assert count('div:only-child') == 22  # ?
        assert count('div:nth-child(even)') == 106
        assert count('div:nth-child(2n)') == 106
        assert count('div:nth-child(odd)') == 137
        assert count('div:nth-child(2n+1)') == 137
        assert count('div:nth-child(n)') == 243
        assert count('div:last-child') == 53
        assert count('div:first-child') == 51
        assert count('div > div') == 242
        assert count('div + div') == 190
        assert count('div ~ div') == 190
        assert count('body') == 1
        assert count('body div') == 243
        assert count('div') == 243
        assert count('div div') == 242
        assert count('div div div') == 241
        assert count('div, div, div') == 243
        assert count('div, a, span') == 243
        assert count('.dialog') == 51
        assert count('div.dialog') == 51
        assert count('div .dialog') == 51
        assert count('div.character, div.dialog') == 99
        assert count('div.direction.dialog') == 0
        assert count('div.dialog.direction') == 0
        assert count('div.dialog.scene') == 1
        assert count('div.scene.scene') == 1
        assert count('div.scene .scene') == 0
        assert count('div.direction .dialog ') == 0
        assert count('div .dialog .direction') == 4
        assert count('div.dialog .dialog .direction') == 4
        assert count('#speech5') == 1
        assert count('div#speech5') == 1
        assert count('div #speech5') == 1
        assert count('div.scene div.dialog') == 49
        assert count('div#scene1 div.dialog div') == 142
        assert count('#scene1 #speech1') == 1
        assert count('div[class]') == 103
        assert count('div[class=dialog]') == 50
        assert count('div[class^=dia]') == 51
        assert count('div[class$=log]') == 50
        assert count('div[class*=sce]') == 1
        assert count('div[class|=dialog]') == 50  # ? Seems right
        assert count('div[class~=dialog]') == 51  # ? Seems right

    # }}}


# Run tests {{{
def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCSSSelectors)


def run_tests(find_tests=find_tests, for_build=False):
    if not for_build:
        parser = argparse.ArgumentParser()
        parser.add_argument('name', nargs='?', default=None,
                            help='The name of the test to run')
        args = parser.parse_args()
    if not for_build and args.name and args.name.startswith('.'):
        tests = find_tests()
        q = args.name[1:]
        if not q.startswith('test_'):
            q = 'test_' + q
        ans = None
        try:
            for test in tests:
                if test._testMethodName == q:
                    ans = test
                    raise StopIteration()
        except StopIteration:
            pass
        if ans is None:
            print('No test named %s found' % args.name)
            raise SystemExit(1)
        tests = ans
    else:
        tests = unittest.defaultTestLoader.loadTestsFromName(args.name) if not for_build and args.name else find_tests()
    r = unittest.TextTestRunner
    if for_build:
        r = r(verbosity=0, buffer=True, failfast=True)
    else:
        r = r(verbosity=4)
    result = r.run(tests)
    if for_build and result.errors or result.failures:
        raise SystemExit(1)


if __name__ == '__main__':
    run_tests()
# }}}
