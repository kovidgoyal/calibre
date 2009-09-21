<?xml version="1.0"?>
<xsl:stylesheet 
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:c="calibre"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:opf="http://www.idpf.org/2007/opf"
    xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata"
    extension-element-prefixes="c"
    xsl:version = "1.1"
>
    <xsl:output method="xml" indent="yes"/>

    <xsl:template match="/">
        <package version="2.0">
            <metadata>
                <xsl:call-template name="make-metadata"/>
            </metadata>
            <manifest>
                <xsl:call-template name="make-manifest"/>
            </manifest>
             <spine toc="ncx">
                <xsl:call-template name="make-spine"/>
            </spine>
        </package>
        <xsl:call-template name="make-ncx"/>
        <xsl:call-template name="make-css"/>
        <xsl:for-each select="//Page">
            <xsl:call-template name="make-page"/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="make-css">
        <xsl:for-each select="//TextStyle|//BlockStyle">
            <c:styles/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="make-page">
        <xsl:variable name="pid" select="@objid"/>
        <xsl:document href="{$pid}.xhtml" method="xml" indent="yes">
            <html>
                <head>
                    <title><xsl:value-of select="//Title"/></title>
                    <link rel="stylesheet" type="text/css" href="styles.css"/>
                </head>
                <body class="body">
                    <xsl:apply-templates />
                </body>
            </html>
        </xsl:document>
    </xsl:template>

    <xsl:template match="RuledLine">
        <c:ruled-line/>
    </xsl:template>

    <xsl:template match="TextBlock">
        <c:text-block/>
    </xsl:template>

    <xsl:template match="ImageBlock">
        <c:image-block/>
    </xsl:template>

    <xsl:template match="Canvas">
        <c:canvas/>
    </xsl:template>

    <xsl:template name="make-metadata">
        <xsl:for-each select='//BookInformation/Info/BookInfo'>
            <xsl:apply-templates select="Title"/>
            <xsl:apply-templates select="Author"/>
            <xsl:apply-templates select="Publisher"/>
            <xsl:apply-templates select="Category|Classification"/>
        </xsl:for-each>
        <xsl:for-each select='//BookInformation/Info/DocInfo'>
            <xsl:apply-templates select="Language"/>
            <xsl:apply-templates select="Producer"/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="Title">
        <xsl:element name="dc:title">
            <xsl:if test="@reading and @reading != ''">
                <xsl:attribute name="opf:file-as"><xsl:value-of select="@reading"/></xsl:attribute>
            </xsl:if>
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="Author">
        <xsl:element name="dc:creator">
            <xsl:attribute name="opf:role">aut</xsl:attribute>
            <xsl:if test="@reading and @reading != ''">
                <xsl:attribute name="opf:file-as"><xsl:value-of select="@reading"/></xsl:attribute>
            </xsl:if>
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="Publisher">
        <xsl:element name="dc:publisher">
            <xsl:if test="@reading and @reading != ''">
                <xsl:attribute name="opf:file-as"><xsl:value-of select="@reading"/></xsl:attribute>
            </xsl:if>
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="Producer">
        <xsl:element name="dc:creator">
            <xsl:attribute name="opf:role">bkp</xsl:attribute>
            <xsl:if test="@reading and @reading != ''">
                <xsl:attribute name="opf:file-as"><xsl:value-of select="@reading"/></xsl:attribute>
            </xsl:if>
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="Language">
        <xsl:element name="dc:language">
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="Category|Classification">
        <xsl:if test=".!=''">
        <xsl:element name="dc:subject">
            <xsl:value-of select="."/>
        </xsl:element>
        </xsl:if>
    </xsl:template>

    <xsl:template name="make-manifest">
        <xsl:for-each select='//Page'>
            <xsl:element name="item">
                <xsl:attribute name="id"><xsl:value-of select="@objid"/></xsl:attribute>
                <xsl:attribute name="media-type"><xsl:text>application/xhtml+xml</xsl:text></xsl:attribute>
                <xsl:attribute name="href"><xsl:value-of select="@objid"/><xsl:text>.xhtml</xsl:text></xsl:attribute>
            </xsl:element>
        </xsl:for-each>
        <xsl:for-each select="//ImageStream">
            <xsl:element name="item">
                <xsl:attribute name="id"><xsl:value-of select="@objid"/></xsl:attribute>
                <xsl:attribute name="media-type"><c:media-type/></xsl:attribute>
                <xsl:attribute name="href"><xsl:value-of select="@file"/></xsl:attribute>
            </xsl:element>
        </xsl:for-each>
        <xsl:for-each select="//RegistFont">
            <xsl:element name="item">
                <xsl:attribute name="id"><xsl:value-of select="@objid"/></xsl:attribute>
                <xsl:attribute name="media-type"><c:media-type/></xsl:attribute>
                <xsl:attribute name="href"><xsl:value-of select="@file"/></xsl:attribute>
            </xsl:element>
        </xsl:for-each>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml" />
        <item id="styles" href="styles.css" media-type="text/css" />

    </xsl:template>

    <xsl:template name="make-spine">
        <xsl:for-each select='//Page'>
            <xsl:element name="itemref">
                <xsl:attribute name="idref"><xsl:value-of select="@objid"/></xsl:attribute>
            </xsl:element>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="*">
        <xsl:message>
            <xsl:text>no match for element: "</xsl:text>
            <xsl:value-of select="name(.)"/>
            <xsl:text>" &#xA;</xsl:text>
        </xsl:message>
        <xsl:apply-templates/>
    </xsl:template>


    <xsl:template name="make-ncx">
        <xsl:document href="toc.ncx" method="xml" indent="yes">
            <ncx version="2005-1" 
                xmlns="http://www.daisy.org/z3986/2005/ncx/"
                xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata"
            >
                <head>
                    <meta name="dtb:uid" content="uid"/>
                    <meta name="dtb:depth" content="1"/>
                    <meta name="dtb:generator" content="calibre"/>
                    <meta name="dtb:totalPageCount" content="0"/>
                    <meta name="dtb:maxPageNumber" content="0"/>
                </head>
                <docTitle><text>Table of Contents</text></docTitle>
                <navMap>
                    <xsl:for-each select="//TOC/TocLabel">
                        <xsl:element name="navPoint">
                            <xsl:attribute name="id"><xsl:value-of select="count(preceding-sibling::*)"/></xsl:attribute>
                            <xsl:attribute name="playOrder"><xsl:value-of select="count(preceding-sibling::*)+1"/></xsl:attribute>
                            <navLabel><text><xsl:value-of select="."/></text></navLabel>
                            <xsl:element name="content">
                                <xsl:attribute name="src">
                                    <xsl:value-of select="@refpage"/>.xhtml#<xsl:value-of select="@refobj"/>
                                </xsl:attribute>
                            </xsl:element>
                        </xsl:element>
                    </xsl:for-each>
                </navMap>
            </ncx>
        </xsl:document>
    </xsl:template>
</xsl:stylesheet>
