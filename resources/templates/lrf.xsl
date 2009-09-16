<?xml version="1.0"?>
<xsl:stylesheet 
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:opf="http://www.idpf.org/2007/opf"
    xmlns:c="calibre"
    extension-element-prefixes="c"
    xsl:version = "1.1"
>
    <xsl:output method="xml" indent="yes"/>

    <xsl:template match="/">
        <package version="2.0" 
            unique-identifier="calibre_id">
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
                <xsl:call-template name="make-metadata"/>
            </metadata>
            <manifest>
                <xsl:call-template name="make-manifest"/>
            </manifest>
             <spine toc="ncx">
                <xsl:call-template name="make-spine"/>
            </spine>
        </package>
    </xsl:template>

    <xsl:template name="make-metadata">
        <xsl:for-each select='//BookInformation/Info'>
            <c:metadata/>
        </xsl:for-each>
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

</xsl:stylesheet>
