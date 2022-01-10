/****************************************************************************
**
** Copyright (C) 2018 The Qt Company Ltd.
** Copyright (C) 2018 Intel Corporation.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the tools applications of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:GPL-EXCEPT$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** GNU General Public License Usage
** Alternatively, this file may be used under the terms of the GNU
** General Public License version 3 as published by the Free Software
** Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
** included in the packaging of this file. Please review the following
** information to ensure the GNU General Public License requirements will
** be met: https://www.gnu.org/licenses/gpl-3.0.html.
**
** $QT_END_LICENSE$
**
****************************************************************************/

// Note: A copy of this file is used in Qt Designer (qttools/src/designer/src/lib/shared/rcc_p.h)

#ifndef RCC_H
#define RCC_H

#include <qstringlist.h>
#include <qhash.h>
#include <qstring.h>

typedef struct ZSTD_CCtx_s ZSTD_CCtx;

QT_BEGIN_NAMESPACE

class RCCFileInfo;
class QIODevice;
class QTextStream;


class RCCResourceLibrary
{
    RCCResourceLibrary(const RCCResourceLibrary &);
    RCCResourceLibrary &operator=(const RCCResourceLibrary &);

public:
    RCCResourceLibrary(quint8 formatVersion=3);
    ~RCCResourceLibrary();

    bool output(QIODevice &outDevice, QIODevice &tempDevice, QIODevice &errorDevice);

    bool readFiles(bool listMode, QIODevice &errorDevice);

    enum Format { Binary, C_Code, Pass1, Pass2, Python_Code };
    void setFormat(Format f) { m_format = f; }
    Format format() const { return m_format; }

    void setInputFiles(const QStringList &files) { m_fileNames = files; }
    QStringList inputFiles() const { return m_fileNames; }

    QStringList dataFiles() const;

    // Return a map of resource identifier (':/newPrefix/images/p1.png') to file.
    typedef QHash<QString, QString> ResourceDataFileMap;
    ResourceDataFileMap resourceDataFileMap() const;

    void setVerbose(bool b) { m_verbose = b; }
    bool verbose() const { return m_verbose; }

    void setInitName(const QString &name) { m_initName = name; }
    QString initName() const { return m_initName; }

    void setOutputName(const QString &name) { m_outputName = name; }
    QString outputName() const { return m_outputName; }

    enum class CompressionAlgorithm {
        Zlib,
        Zstd,

        Best = 99,
        None = -1
    };

    static CompressionAlgorithm parseCompressionAlgorithm(QStringView algo, QString *errorMsg);
    void setCompressionAlgorithm(CompressionAlgorithm algo) { m_compressionAlgo = algo; }
    CompressionAlgorithm compressionAlgorithm() const { return m_compressionAlgo; }

    static int parseCompressionLevel(CompressionAlgorithm algo, const QString &level, QString *errorMsg);
    void setCompressLevel(int c) { m_compressLevel = c; }
    int compressLevel() const { return m_compressLevel; }

    void setCompressThreshold(int t) { m_compressThreshold = t; }
    int compressThreshold() const { return m_compressThreshold; }

    void setResourceRoot(const QString &root) { m_resourceRoot = root; }
    QString resourceRoot() const { return m_resourceRoot; }

    void setUseNameSpace(bool v) { m_useNameSpace = v; }
    bool useNameSpace() const { return m_useNameSpace; }

    QStringList failedResources() const { return m_failedResources; }

    int formatVersion() const { return m_formatVersion; }

    void setNoZstd(bool v) { m_noZstd = v; }
    bool noZstd() const { return m_noZstd; }

private:
    struct Strings {
        Strings();
        const QString TAG_RCC;
        const QString TAG_RESOURCE;
        const QString TAG_FILE;
        const QString ATTRIBUTE_LANG;
        const QString ATTRIBUTE_PREFIX;
        const QString ATTRIBUTE_ALIAS;
        const QString ATTRIBUTE_THRESHOLD;
        const QString ATTRIBUTE_COMPRESS;
        const QString ATTRIBUTE_COMPRESSALGO;
    };
    friend class RCCFileInfo;
    void reset();
    bool addFile(const QString &alias, const RCCFileInfo &file);
    bool interpretResourceFile(QIODevice *inputDevice, const QString &file,
        QString currentPath = QString(), bool listMode = false);
    bool writeHeader();
    bool writeDataBlobs();
    bool writeDataNames();
    bool writeDataStructure();
    bool writeInitializer();
    void writeMangleNamespaceFunction(const QByteArray &name);
    void writeAddNamespaceFunction(const QByteArray &name);
    void writeDecimal(int value);
    void writeHex(quint8 number);
    void write2HexDigits(quint8 number);
    void writeNumber2(quint16 number);
    void writeNumber4(quint32 number);
    void writeNumber8(quint64 number);
    void writeChar(char c) { m_out.append(c); }
    void writeByteArray(const QByteArray &);
    void write(const char *, int len);
    void writeString(const char *s) { write(s, static_cast<int>(strlen(s))); }

    const Strings m_strings;
    RCCFileInfo *m_root;
    QStringList m_fileNames;
    QString m_resourceRoot;
    QString m_initName;
    QString m_outputName;
    Format m_format;
    bool m_verbose;
    CompressionAlgorithm m_compressionAlgo;
    int m_compressLevel;
    int m_compressThreshold;
    int m_treeOffset;
    int m_namesOffset;
    int m_dataOffset;
    quint32 m_overallFlags;
    bool m_useNameSpace;
    QStringList m_failedResources;
    QIODevice *m_errorDevice;
    QIODevice *m_outDevice;
    QByteArray m_out;
    quint8 m_formatVersion;
    bool m_noZstd;
};

QT_END_NAMESPACE

#endif // RCC_H
