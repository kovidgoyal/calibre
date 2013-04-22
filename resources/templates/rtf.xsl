<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns="http://www.w3.org/1999/xhtml"
    xmlns:rtf="http://rtf2xml.sourceforge.net/"
    xmlns:c="calibre"
    extension-element-prefixes="c"
    exclude-result-prefixes="rtf"
>

    <xsl:template match = "rtf:para">
        <xsl:choose>
            <xsl:when test = "parent::rtf:paragraph-definition[@name='heading 1']|
                              parent::rtf:paragraph-definition[@name='heading 2']|
                              parent::rtf:paragraph-definition[@name='heading 3']|
                              parent::rtf:paragraph-definition[@name='heading 4']|
                              parent::rtf:paragraph-definition[@name='heading 5']|
                              parent::rtf:paragraph-definition[@name='heading 6']|
                              parent::rtf:paragraph-definition[@name='heading 7']|
                              parent::rtf:paragraph-definition[@name='heading 8']|
                              parent::rtf:paragraph-definition[@name='heading 9']

            ">
                <xsl:variable name="head-number" select="substring(parent::rtf:paragraph-definition/@name, 9)"/>
                <xsl:element name="h{$head-number}">
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:call-template name = "para"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="rtf:style-group">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="rtf:paragraph-definition">
        <xsl:choose>
            <xsl:when test = "parent::rtf:paragraph-definition[@name='heading 1']|
                              parent::rtf:paragraph-definition[@name='heading 2']|
                              parent::rtf:paragraph-definition[@name='heading 3']|
                              parent::rtf:paragraph-definition[@name='heading 4']|
                              parent::rtf:paragraph-definition[@name='heading 5']|
                              parent::rtf:paragraph-definition[@name='heading 6']|
                              parent::rtf:paragraph-definition[@name='heading 7']|
                              parent::rtf:paragraph-definition[@name='heading 8']|
                              parent::rtf:paragraph-definition[@name='heading 9']

            ">
                <xsl:apply-templates/>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="div">
                    <xsl:attribute name="class">
                        <xsl:value-of select="@style-number"/>
                    </xsl:attribute>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template name = "para">
        <xsl:element name = "p">
            <xsl:choose>
                <xsl:when test = "normalize-space(.) or child::*">
                    <xsl:call-template name = "para-content"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:text>&#160;</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:element>
    </xsl:template>

    <xsl:template name = "para_off">
        <xsl:if test = "normalize-space(.) or child::*">
            <xsl:element name = "p">
                <xsl:attribute name = "class">
                    <xsl:value-of select = "../@style-number"/>
                </xsl:attribute>
                <xsl:call-template name = "para-content"/>
            </xsl:element>
        </xsl:if>
    </xsl:template>


    <xsl:template name = "para-content">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template name = "para-content_off">
        <xsl:choose>
            <xsl:when test = "@italics = 'true' ">
               <emph rend = "paragraph-emph-italics">
                    <xsl:apply-templates/>
               </emph>
            </xsl:when>
            <xsl:when test = "@bold = 'true' ">
               <emph rend = "paragraph-emph-bold">
                    <xsl:apply-templates/>
               </emph>
            </xsl:when>
            <xsl:when test = "@underlined and @underlined != 'false'">
               <emph rend = "paragraph-emph-underlined">
                    <xsl:apply-templates/>
               </emph>
            </xsl:when>
            <xsl:when test = "(@strike-through = 'true')
                or (@double-strike-through = 'true')
                or (@emboss = 'true')
                or (@engrave = 'true')
                or (@small-caps = 'true')
                or (@shadow = 'true')
                or (@hidden = 'true')
                or (@outline = 'true')
                ">
               <emph rend = "paragraph-emph">
                    <xsl:apply-templates/>
               </emph>
            </xsl:when>
            <xsl:otherwise>
                <xsl:apply-templates/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template name="make-header">
        <head>
            <xsl:element name="meta">
                <xsl:attribute name="name">
                    <xsl:text>generator</xsl:text>
                </xsl:attribute>
                <xsl:attribute name="content">
                    <xsl:text>http://calibre-ebook.com</xsl:text>
                </xsl:attribute>
            </xsl:element>

            <xsl:choose>
                <xsl:when test="/rtf:doc/rtf:preamble/rtf:doc-information">
                    <xsl:apply-templates select="/rtf:doc/rtf:preamble/rtf:doc-information" mode="header"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:call-template name="html-head"/>
                </xsl:otherwise>
            </xsl:choose>
        </head>
    </xsl:template>

    <xsl:template match="rtf:doc-information"/>

    <xsl:template match="rtf:doc-information" mode="header">
          <link rel="stylesheet" type="text/css" href="styles.css"/>
          <xsl:if test="not(rtf:title)">
              <title>unnamed</title>
          </xsl:if>
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="rtf:creation-time|rtf:doc-notes|rtf:author|rtf:revision-time">
        <xsl:element name="meta">
            <xsl:attribute name="name">
                <xsl:value-of select="name(.)"/>
            </xsl:attribute>
            <xsl:attribute name="content">
                <xsl:apply-templates/>
            </xsl:attribute>
        </xsl:element>
    </xsl:template>

    <xsl:template match="rtf:creation-time|rtf:revision-time">
        <xsl:element name="meta">
            <xsl:attribute name="name">
                <xsl:value-of select="name(.)"/>
            </xsl:attribute>
            <xsl:attribute name="content">
                <xsl:value-of select="@year"/>
                <xsl:text>-</xsl:text>
                <xsl:value-of select="@month"/>
                <xsl:text>-</xsl:text>
                <xsl:value-of select="@day"/>
            </xsl:attribute>
        </xsl:element>
    </xsl:template>

    <xsl:template match="rtf:operator|rtf:editing-time|rtf:number-of-pages|rtf:number-of-words|rtf:number-of-characters"/>


    <xsl:template match="rtf:title">
        <xsl:element name="title">
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>


    <xsl:template name="html-head">
        <title>unnamed</title>
          <link rel="stylesheet" type="text/css" href="styles.css"/>
    </xsl:template>

    <xsl:template name="make-css-stylesheet">
        <xsl:document href="styles.css" method="text">
            <xsl:for-each select="//rtf:paragraph-definition">
                <xsl:if test = "generate-id(.) = generate-id(key('style-types', @style-number))">
                    <xsl:text>div.</xsl:text>
                    <xsl:value-of select="@style-number"/>
                    <xsl:text>{</xsl:text>
                    <xsl:call-template name="parse-styles-attrs"/>
                    <xsl:text>}&#xA;</xsl:text>
                </xsl:if>
            </xsl:for-each>
            <xsl:text>span.italic{font-style:italic}&#xA;</xsl:text>
            <xsl:text>span.no-italic{font-style:normal}&#xA;</xsl:text>
            <xsl:text>span.bold{font-weight:bold}&#xA;</xsl:text>
            <xsl:text>span.no-bold{font-weight:normal}&#xA;</xsl:text>
            <xsl:text>span.underline{text-decoration:underline}&#xA;</xsl:text>
            <xsl:text>span.no-underline{text-decoration:none}&#xA;</xsl:text>
            <xsl:text>span.italic-bold{font-style:italic;font-weight:bold}&#xA;</xsl:text>
            <xsl:text>span.italic-underline{font-style:italic;text-decoration:underline}&#xA;</xsl:text>
            <xsl:text>span.bold-underline{font-weight:bold;text-decoration:underline}&#xA;</xsl:text>
            <xsl:text>&#xA;</xsl:text>
        </xsl:document>
    </xsl:template>

    <xsl:template name="parse-styles-attrs">
        <!--<xsl:text>position:relative;</xsl:text>
        <xsl:if test="@space-before">
            <xsl:text>padding-top:</xsl:text>
            <xsl:value-of select="@space-before"/>
            <xsl:text>pt;</xsl:text>
        </xsl:if>
        <xsl:if test="@space-after">
            <xsl:text>padding-bottom:</xsl:text>
            <xsl:value-of select="@space-after"/>
            <xsl:text>pt;</xsl:text>
        </xsl:if>-->
        <xsl:if test="@left-indent">
            <xsl:text>padding-left:</xsl:text>
            <xsl:value-of select="@left-indent"/>
            <xsl:text>pt;</xsl:text>
        </xsl:if>
        <xsl:if test="@right-indent">
            <xsl:text>padding-right:</xsl:text>
            <xsl:value-of select="@right-indent"/>
            <xsl:text>pt;</xsl:text>
        </xsl:if>
        <xsl:if test="@first-line-indent">
            <xsl:text>text-indent:</xsl:text>
            <xsl:value-of select="@first-line-indent"/>
            <xsl:text>pt;</xsl:text>
        </xsl:if>
        <xsl:if test="@bold='true'">
            <xsl:text>font-weight:</xsl:text>
            <xsl:value-of select="'bold'"/>
            <xsl:text>;</xsl:text>
        </xsl:if>
        <xsl:if test="@italics='true'">
            <xsl:text>font-style:</xsl:text>
            <xsl:value-of select="'italic'"/>
            <xsl:text>;</xsl:text>
        </xsl:if>
        <xsl:if test="@underlined and @underlined != 'false'">
            <xsl:text>text-decoration:underline</xsl:text>
            <xsl:text>;</xsl:text>
        </xsl:if>
        <!--<xsl:if test="@line-spacing">
            <xsl:text>line-height:</xsl:text>
            <xsl:value-of select="@line-spacing"/>
            <xsl:text>pt;</xsl:text>
        </xsl:if>-->
        <xsl:if test="(@align = 'just')">
            <xsl:text>text-align: justify;</xsl:text>
        </xsl:if>
        <xsl:if test="(@align = 'cent')">
            <xsl:text>text-align: center;</xsl:text>
        </xsl:if>
        <xsl:if test="(@align = 'left')">
            <xsl:text>text-align: left;</xsl:text>
        </xsl:if>
        <xsl:if test="(@align = 'right')">
            <xsl:text>text-align: right;</xsl:text>
        </xsl:if>
    </xsl:template>

    <xsl:template match="rtf:inline">
        <xsl:variable name="num-attrs" select="count(@*)"/>
        <xsl:choose>
            <xsl:when test="@footnote-marker">
                <xsl:text>[</xsl:text>
                <xsl:value-of select="count(preceding::rtf:footnote) + 1"/>
                <xsl:text>]</xsl:text>
            </xsl:when>
            <xsl:when test="(@superscript)">
                <xsl:element name="sup">
                    <xsl:element name="span">
                        <xsl:attribute name="class">
                            <c:inline-class/>
                        </xsl:attribute>
                        <xsl:apply-templates/>
                    </xsl:element>
                </xsl:element>
            </xsl:when>
            <xsl:when test="(@underscript or @subscript)">
                <xsl:element name="sub">
                    <xsl:element name="span">
                        <xsl:attribute name="class">
                            <c:inline-class/>
                        </xsl:attribute>
                        <xsl:apply-templates/>
                    </xsl:element>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="span">
                    <xsl:attribute name="class">
                        <c:inline-class/>
                    </xsl:attribute>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="rtf:footnote"/>

    <xsl:template match="rtf:footnote" mode="bottom">
        <xsl:element name="div">
            <xsl:attribute name="class">
                <xsl:text>footnote</xsl:text>
            </xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>

    </xsl:template>

       <xsl:template match="rtf:list[@list-type='unordered']">
       <xsl:element name="ul">
           <xsl:apply-templates/>
       </xsl:element>
   </xsl:template>

   <xsl:template match="rtf:list[@list-type='ordered']">
       <xsl:element name="ol">
           <xsl:apply-templates/>
       </xsl:element>
   </xsl:template>

   <xsl:template match="rtf:item">
       <xsl:element name="li">
           <xsl:apply-templates/>
       </xsl:element>
   </xsl:template>

   <xsl:template match="rtf:item/rtf:style-group/rtf:paragraph-definition/rtf:para" priority="2">
       <xsl:apply-templates/>
   </xsl:template>

    <xsl:template match="rtf:table">
        <xsl:element name="table">
            <xsl:attribute name="id">
                <xsl:value-of select="generate-id(.)"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="rtf:row">
        <xsl:element name="tr">
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="rtf:cell">
        <xsl:element name="td">
            <xsl:if test="@class">
                <xsl:attribute name="class"><xsl:value-of select="@class"/></xsl:attribute>
            </xsl:if>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <!--
    <xsl:include href="blocks.xsl"/>
    <xsl:include href="fields.xsl"/>
    -->




    <xsl:output method = "xml"/>
    <xsl:key name="style-types" match="rtf:paragraph-definition" use="@style-number"/>


    <xsl:variable name = "delete-list-text">true</xsl:variable>
    <xsl:variable name = "delete-field-blocks">true</xsl:variable>
    <xsl:variable name = "delete-annotation">false</xsl:variable>

    <xsl:template match="/">
        <xsl:call-template name="make-css-stylesheet"/>
        <html>
            <xsl:call-template name="make-header"/>
            <xsl:apply-templates/>
        </html>
    </xsl:template>

    <xsl:template match="rtf:doc">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="rtf:preamble">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="rtf:page-break">
        <br style = "page-break-after:always"/>
    </xsl:template>
    
    <xsl:template match="rtf:hardline-break">
        <br/>
    </xsl:template>

    <xsl:template match="rtf:rtf-definition|rtf:font-table|rtf:color-table|rtf:style-table|rtf:page-definition|rtf:list-table|rtf:override-table|rtf:override-list|rtf:list-text"/>

    <xsl:template match="rtf:body">
        <xsl:element name="body">
            <xsl:apply-templates/>
            <xsl:if test = "//rtf:footnote">
                <hr/>
            </xsl:if>
            <xsl:for-each select="//rtf:footnote">
                <xsl:apply-templates select="." mode="bottom"/>
            </xsl:for-each>
        </xsl:element>
    </xsl:template>

    <xsl:template match="rtf:section">
        <xsl:element name="div">
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match = "rtf:field-block">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match = "rtf:field[@type='hyperlink']">
        <xsl:element name ="a">
            <xsl:attribute name = "href">
                <xsl:choose>
                <xsl:when test="@argument">
                    <xsl:value-of select="@argument"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:if test = "not(contains(@link, '/'))">#</xsl:if>
                    <xsl:value-of select = "@link"/>
                </xsl:otherwise>
            </xsl:choose>
            </xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
	
    <xsl:template match = "rtf:field[@type='bookmark-start']">
        <xsl:element name ="a">
            <xsl:attribute name = "id">
               <xsl:value-of select = "@number"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match = "rtf:field">
        <xsl:apply-templates/>
    </xsl:template>

    <xsl:template match="rtf:pict">
        <img src = "{@num}"/>
    </xsl:template>

    <xsl:template match="*">
        <xsl:message>
            <xsl:text>no match for element: "</xsl:text>
            <xsl:value-of select="name(.)"/>
            <xsl:text>" &#xA;</xsl:text>
        </xsl:message>
        <xsl:apply-templates/>
    </xsl:template>

</xsl:stylesheet>
