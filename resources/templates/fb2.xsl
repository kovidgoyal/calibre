<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:fb="http://www.gribuser.ru/xml/fictionbook/2.0">
<!--
#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#   Copyright 2011 Kovid Goyal
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#   You should have received a copy of the GNU General Public License   #
#   along with this program; if not, write to the Free Software         #
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA            #
#   02111-1307 USA                                                      #
#                                                                       #
#                                                                       #
#########################################################################

-->
    <xsl:output method="xml" encoding="UTF-8"/>
    <xsl:key name="note-link" match="fb:section" use="@id"/>
    <xsl:template match="/*">
        <html>
            <head>
                <xsl:if test="fb:description/fb:title-info/fb:lang = 'ru'">
                    <meta HTTP-EQUIV="content-type" CONTENT="text/html; charset=UTF-8"/>
                </xsl:if>
                <title>
                    <xsl:value-of select="fb:description/fb:title-info/fb:book-title"/>
                </title>
                <style type="text/css">
                    body { text-align : justify }
                    
                    h1{ font-size : 160%; font-style : normal; font-weight : bold; text-align : left; border : 1px solid Black;  background-color : #E7E7E7; margin-left : 0px;  page-break-before : always; }
                    
                    h2{ font-size : 130%; font-style : normal; font-weight : bold; text-align : left; background-color : #EEEEEE;  border : 1px solid Gray;  page-break-before : always; }
                    h3{ font-size : 110%; font-style : normal; font-weight : bold; text-align : left;  background-color : #F1F1F1;  border : 1px solid Silver;}
                    
                    h4{ font-size : 100%; font-style : normal; font-weight : bold; text-align : left; border : 1px solid Gray;  background-color : #F4F4F4;}
                    
                    h5{ font-size : 100%; font-style : italic; font-weight : bold; text-align : left; border : 1px solid Gray;  background-color : #F4F4F4;}
                    
                    h6{ font-size : 100%; font-style : italic; font-weight : normal; text-align : left; border : 1px solid Gray;  background-color : #F4F4F4;}
                    
                    small { font-size : 80% }
                    
                    blockquote { margin-left :4em; margin-top:1em; margin-right:0.2em;}
                    
                    hr { color : Black }
                    
                    ul {margin-left: 0}
                    
                    .epigraph{width:75%; margin-left : 25%; font-style: italic;}
                    
                    div.paragraph { text-indent: 2em; }

                    .subtitle { text-align: center; }
                </style>
                <link rel="stylesheet" type="text/css" href="inline-styles.css" />
            </head>
            <body>
                <xsl:for-each select="fb:description/fb:title-info/fb:annotation">
                    <div>
                        <xsl:call-template name="annotation"/>
                    </div>
                    <hr/>
                </xsl:for-each>
                <!-- BUILD TOC -->
                <ul>
                    <xsl:apply-templates select="fb:body" mode="toc"/>
                </ul>
                <hr/>
                <!-- END BUILD TOC -->
                <!-- BUILD BOOK -->
                <xsl:for-each select="fb:body">
                    <xsl:if test="position()!=1">
                        <hr/>
                    </xsl:if>
                    <xsl:if test="@name">
                        <h4 align="center">
                            <xsl:value-of select="@name"/>
                        </h4>
                    </xsl:if>
                    <!-- <xsl:apply-templates /> -->
                    <xsl:apply-templates/>
                </xsl:for-each>
            </body>
        </html>
    </xsl:template>
    <!-- author template -->
    <xsl:template name="author">
        <xsl:value-of select="fb:first-name"/>
        <xsl:text disable-output-escaping="no">&#032;</xsl:text>
        <xsl:value-of select="fb:middle-name"/>&#032;
         <xsl:text disable-output-escaping="no">&#032;</xsl:text>
        <xsl:value-of select="fb:last-name"/>
        <br/>
    </xsl:template>
    <!-- secuence template -->
    <xsl:template name="sequence">
        <li/>
        <xsl:value-of select="@name"/>
        <xsl:if test="@number">
            <xsl:text disable-output-escaping="no">,&#032;#</xsl:text>
            <xsl:value-of select="@number"/>
        </xsl:if>
        <xsl:if test="fb:sequence">
            <ul>
                <xsl:for-each select="fb:sequence">
                    <xsl:call-template name="sequence"/>
                </xsl:for-each>
            </ul>
        </xsl:if>
        <!--      <br/> -->
    </xsl:template>
    <!-- toc template -->
    <xsl:template match="fb:section|fb:body" mode="toc">
        <xsl:choose>
            <xsl:when test="name()='body' and position()=1 and not(fb:title)">
                <xsl:apply-templates select="fb:section" mode="toc"/>
            </xsl:when>
            <xsl:otherwise>
                <li>
                    <a href="#TOC_{generate-id()}"><xsl:value-of select="normalize-space(fb:title/fb:p[1] | @name)"/></a>
                    <xsl:if test="fb:section">
                        <ul><xsl:apply-templates select="fb:section" mode="toc"/></ul>
                    </xsl:if>
                </li>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <!-- description -->
    <xsl:template match="fb:description">
        <xsl:apply-templates/>
    </xsl:template>
    <!-- body -->
    <xsl:template match="fb:body">
        <div><xsl:apply-templates/></div>
    </xsl:template>

    <xsl:template match="fb:section">
        <xsl:variable name="section_has_title">
            <xsl:choose>
                <xsl:when test="./fb:title"><xsl:value-of select="generate-id()" /></xsl:when>
                <xsl:otherwise>None</xsl:otherwise>
            </xsl:choose>
        </xsl:variable>
        <xsl:if test="$section_has_title = 'None'">
            <div id="TOC_{generate-id()}">
                <xsl:if test="@id">
                    <xsl:element name="a">
                        <xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute>
                    </xsl:element>
                </xsl:if>
            </div>
        </xsl:if>
        <xsl:apply-templates>
            <xsl:with-param name="section_toc_id" select="$section_has_title" />
        </xsl:apply-templates>
    </xsl:template>
    
    
    <!-- section/title -->
    <xsl:template match="fb:section/fb:title|fb:poem/fb:title">
        <xsl:param name="section_toc_id" />
        <xsl:choose>
            <xsl:when test="count(ancestor::node()) &lt; 9">
                <xsl:element name="{concat('h',count(ancestor::node())-3)}">
                    <xsl:if test="../@id">
                        <xsl:attribute name="id"><xsl:value-of select="../@id" /></xsl:attribute>
                    </xsl:if>
                    <xsl:if test="$section_toc_id != 'None'">
                        <xsl:element name="a">
                            <xsl:attribute name="id">TOC_<xsl:value-of select="$section_toc_id"/></xsl:attribute>
                        </xsl:element>
                    </xsl:if>
                    <a name="TOC_{generate-id()}"></a>
                    <xsl:if test="@id">
                        <xsl:element name="a">
                            <xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute>
                        </xsl:element>
                    </xsl:if>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="h6">
                    <xsl:if test="@id">
                        <xsl:element name="a">
                            <xsl:attribute name="id"><xsl:value-of select="@id"/></xsl:attribute>
                        </xsl:element>
                    </xsl:if>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <!-- section/title -->
    <xsl:template match="fb:body/fb:title">
        <xsl:element name="h1">
            <xsl:apply-templates />
        </xsl:element>
    </xsl:template>

    <xsl:template match="fb:title/fb:p">
        <xsl:apply-templates/><xsl:text disable-output-escaping="no">&#032;</xsl:text><br/>
    </xsl:template>
    <!-- subtitle -->
    <xsl:template match="fb:subtitle">
        <xsl:if test="@id">
            <xsl:element name="a">
                <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
            </xsl:element>
        </xsl:if>
        <h5 class="subtitle">
            <xsl:apply-templates/>
        </h5>
    </xsl:template>
    <!-- p -->
    <xsl:template match="fb:p">
        <xsl:element name="div">
            <xsl:attribute name="class">paragraph</xsl:attribute>
            <xsl:if test="@id">
                <xsl:element name="a">
                    <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
                </xsl:element>
            </xsl:if>
            <xsl:if test="@style">
                <xsl:attribute name="style"><xsl:value-of select="@style"/></xsl:attribute>
            </xsl:if>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    <!-- strong -->
    <xsl:template match="fb:strong">
        <strong><xsl:apply-templates/></strong>
    </xsl:template>
    <!-- emphasis -->
    <xsl:template match="fb:emphasis">
        <em> <xsl:apply-templates/></em>
    </xsl:template>
    <!-- style -->
    <xsl:template match="fb:style">
        <span class="{@name}"><xsl:apply-templates/></span>
    </xsl:template>
    <!-- empty-line -->
    <xsl:template match="fb:empty-line">
        <br/>
    </xsl:template>
    <!-- super/sub-scripts -->
    <xsl:template match="fb:sup">
        <sup><xsl:apply-templates/></sup>
    </xsl:template>
    <xsl:template match="fb:sub">
        <sub><xsl:apply-templates/></sub>
    </xsl:template>
    <!-- link -->
    <xsl:template match="fb:a">
        <xsl:element name="a">
            <xsl:attribute name="href"><xsl:value-of select="@xlink:href"/></xsl:attribute>
            <xsl:attribute name="title">
                <xsl:choose>
                    <xsl:when test="starts-with(@xlink:href,'#')"><xsl:value-of select="key('note-link',substring-after(@xlink:href,'#'))/fb:p"/></xsl:when>
                    <xsl:otherwise><xsl:value-of select="key('note-link',@xlink:href)/fb:p"/></xsl:otherwise>
                </xsl:choose>
            </xsl:attribute>
            <xsl:choose>
                <xsl:when test="(@type) = 'note'">
                    <sup>
                        <xsl:apply-templates/>
                    </sup>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:element>
    </xsl:template>
    <!-- annotation -->
    <xsl:template name="annotation">
        <xsl:if test="@id">
            <xsl:element name="a">
                <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
            </xsl:element>
        </xsl:if>
        <h3>Annotation</h3>
        <xsl:apply-templates/>
    </xsl:template>
    <!-- tables -->
    <xsl:template match="fb:table">
        <table>
            <xsl:apply-templates/>
        </table>
    </xsl:template>
    <xsl:template match="fb:tr">
        <xsl:element name="tr">
            <xsl:if test="@align">
                <xsl:attribute name="align"><xsl:value-of select="@align"/></xsl:attribute>
            </xsl:if>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    <xsl:template match="fb:td|fb:th">
        <xsl:element name="{local-name()}">
            <xsl:if test="@align">
                <xsl:attribute name="align"><xsl:value-of select="@align"/></xsl:attribute>
            </xsl:if>
            <xsl:if test="@style">
                <xsl:attribute name="style"><xsl:value-of select="@style"/></xsl:attribute>
            </xsl:if>
            <xsl:if test="@colspan">
                <xsl:attribute name="colspan"><xsl:value-of select="@colspan"/></xsl:attribute>
            </xsl:if>
            <xsl:if test="@rowspan">
                <xsl:attribute name="rowspan"><xsl:value-of select="@rowspan"/></xsl:attribute>
            </xsl:if>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    <!-- epigraph -->
    <xsl:template match="fb:epigraph">
        <blockquote class="epigraph">
            <xsl:if test="@id">
                <xsl:element name="a">
                    <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
                </xsl:element>
            </xsl:if>
            <xsl:apply-templates/>
        </blockquote>
    </xsl:template>
    <!-- epigraph/text-author -->
    <xsl:template match="fb:epigraph/fb:text-author">
        <blockquote>
            <i><xsl:apply-templates/></i>
        </blockquote>
    </xsl:template>
    <!-- cite -->
    <xsl:template match="fb:cite">
        <blockquote>
        <xsl:if test="@id">
            <xsl:element name="a">
                <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
            </xsl:element>
        </xsl:if>
        <xsl:apply-templates/>
        </blockquote>
    </xsl:template>
    <!-- cite/text-author -->
    <xsl:template match="fb:text-author">
        <blockquote>
        <i> <xsl:apply-templates/></i></blockquote>
    </xsl:template>
    <!-- date -->
    <xsl:template match="fb:date">
        <xsl:choose>
            <xsl:when test="not(@value)">
                &#160;&#160;&#160;<xsl:apply-templates/>
                <br/>
            </xsl:when>
            <xsl:otherwise>
                &#160;&#160;&#160;<xsl:value-of select="@value"/>
                <br/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    <!-- poem -->
    <xsl:template match="fb:poem">
        <blockquote>
            <xsl:if test="@id">
                <xsl:element name="a">
                    <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
                </xsl:element>
            </xsl:if>
            <xsl:apply-templates/>
        </blockquote>
    </xsl:template>

    <!-- stanza -->
    <xsl:template match="fb:stanza">
        <xsl:apply-templates/>
        <br/>
    </xsl:template>
    <!-- v -->
    <xsl:template match="fb:v">
        <xsl:if test="@id">
            <xsl:element name="a">
                <xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute>
            </xsl:element>
        </xsl:if>
        <xsl:apply-templates/><br/>
    </xsl:template>
    <!-- image -->
    <xsl:template match="fb:body/fb:image|fb:section/fb:image">
        <div align="center">
            <xsl:element name="img">
                <xsl:attribute name="border">1</xsl:attribute>
                <xsl:choose>
                    <xsl:when test="starts-with(@xlink:href,'#')">
                        <xsl:attribute name="src"><xsl:value-of select="substring-after(@xlink:href,'#')"/></xsl:attribute>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:attribute name="src"><xsl:value-of select="@xlink:href"/></xsl:attribute>
                    </xsl:otherwise>
                </xsl:choose>
                <xsl:if test="@title">
                    <xsl:attribute name="title"><xsl:value-of select="@title"/></xsl:attribute>
                </xsl:if>
            </xsl:element>
        </div>
    </xsl:template>
    <xsl:template match="fb:image">
            <xsl:element name="img">
                <xsl:choose>
                    <xsl:when test="starts-with(@xlink:href,'#')">
                        <xsl:attribute name="src"><xsl:value-of select="substring-after(@xlink:href,'#')"/></xsl:attribute>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:attribute name="src"><xsl:value-of select="@xlink:href"/></xsl:attribute>
                    </xsl:otherwise>
                </xsl:choose>
                <xsl:if test="@title">
                    <xsl:attribute name="title"><xsl:value-of select="@title"/></xsl:attribute>
                </xsl:if>
            </xsl:element>
    </xsl:template>
    <!-- code -->
    <xsl:template match="fb:code">
        <code><xsl:apply-templates/></code>
    </xsl:template>
    <!-- Strikethrough text -->
    <xsl:template match="fb:strikethrough">
        <del><xsl:apply-templates/></del>
    </xsl:template>

</xsl:stylesheet>
