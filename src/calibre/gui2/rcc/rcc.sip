// Copyright (c) 2021 Riverbank Computing Limited <info@riverbankcomputing.com>
// 
// This file may be used under the terms of the GNU General Public License
// version 3.0 as published by the Free Software Foundation and appearing in
// the file LICENSE included in the packaging of this file.  Please review the
// following information to ensure the GNU General Public License version 3.0
// requirements will be met: http://www.gnu.org/copyleft/gpl.html.
// 
// If you do not wish to use this file under the terms of the GPL version 3.0
// then you may purchase a commercial license.  For more information contact
// info@riverbankcomputing.com.
// 
// This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
// WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.


%Module(name=rcc_backend)

%Import QtCore/QtCoremod.sip


class RCCResourceLibrary /NoDefaultCtors/
{
%TypeHeaderCode
#include "rcc.h"
%End

public:
    RCCResourceLibrary(quint8 formatVersion);
    ~RCCResourceLibrary();


    bool output(QIODevice &outDevice, QIODevice &tempDevice, QIODevice &errorDevice);
    bool readFiles(bool listMode, QIODevice &errorDevice);

    void setInputFiles(QStringList files);
    enum Format { Binary, C_Code, Pass1, Pass2, Python_Code };
    void setFormat(Format f); 
    Format format(); 

    enum class CompressionAlgorithm {
        Zlib,
        Zstd,

        Best = 99,
        None = -1
    };

    void setCompressionAlgorithm(CompressionAlgorithm algo);
    CompressionAlgorithm compressionAlgorithm() const;

    QStringList dataFiles() const;

    void setVerbose(bool b);
	bool verbose() const;
    void setResourceRoot(const QString &root); 
    QString resourceRoot();

    void setInitName(const QString &name); 
    QString initName() const;

    void setOutputName(const QString &name);
    QString outputName() const;

    void setUseNameSpace(bool v);
    bool useNameSpace() const;

    QStringList failedResources() const;

    int formatVersion() const;

    void setNoZstd(bool v);
    bool noZstd() const;
};
