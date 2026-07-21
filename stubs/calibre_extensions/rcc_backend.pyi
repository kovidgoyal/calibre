import enum

from qt.core import QIODevice

class RCCResourceLibrary:
    "Wraps Qt's rcc tool to compile .qrc resource files into a binary or source resource format"

    class Format(enum.Enum):
        Binary = enum.auto()
        C_Code = enum.auto()
        Pass1 = enum.auto()
        Pass2 = enum.auto()
        Python_Code = enum.auto()

    class CompressionAlgorithm(enum.Enum):
        Zlib = enum.auto()
        Zstd = enum.auto()
        Best = 99
        None_ = -1

    def __init__(self, formatVersion: int = 3) -> None:
        "Create a new RCCResourceLibrary with the specified resource format version"
        pass

    def output(self, outDevice: QIODevice, tempDevice: QIODevice, errorDevice: QIODevice) -> bool:
        "Write the compiled resources to outDevice, using tempDevice as scratch space and reporting errors on errorDevice"
        pass

    def readFiles(self, listMode: bool, errorDevice: QIODevice) -> bool:
        "Read the input .qrc files previously set with setInputFiles(), reporting errors on errorDevice"
        pass

    def setInputFiles(self, files: list[str]) -> None:
        "Set the list of paths to .qrc files to be compiled"
        pass

    def setFormat(self, f: Format) -> None:
        "Set the output format"
        pass

    def format(self) -> Format:
        "Return the output format"
        pass

    def setCompressionAlgorithm(self, algo: CompressionAlgorithm) -> None:
        "Set the compression algorithm used for resource data"
        pass

    def compressionAlgorithm(self) -> CompressionAlgorithm:
        "Return the compression algorithm used for resource data"
        pass

    def dataFiles(self) -> list[str]:
        "Return the list of data files referenced by the input .qrc files"
        pass

    def setVerbose(self, b: bool) -> None:
        "Set whether verbose diagnostic output is produced"
        pass

    def verbose(self) -> bool:
        "Return whether verbose diagnostic output is produced"
        pass

    def setResourceRoot(self, root: str) -> None:
        "Set the root path resource file paths are made relative to"
        pass

    def resourceRoot(self) -> str:
        "Return the root path resource file paths are made relative to"
        pass

    def setInitName(self, name: str) -> None:
        "Set the name used for the generated initialization function, for C_Code output"
        pass

    def initName(self) -> str:
        "Return the name used for the generated initialization function"
        pass

    def setOutputName(self, name: str) -> None:
        "Set the name of the output file"
        pass

    def outputName(self) -> str:
        "Return the name of the output file"
        pass

    def setUseNameSpace(self, v: bool) -> None:
        "Set whether generated C++ code is wrapped in a namespace"
        pass

    def useNameSpace(self) -> bool:
        "Return whether generated C++ code is wrapped in a namespace"
        pass

    def failedResources(self) -> list[str]:
        "Return the list of resources that failed to be read"
        pass

    def formatVersion(self) -> int:
        "Return the resource format version"
        pass

    def setNoZstd(self, v: bool) -> None:
        "Set whether zstd compression is disabled"
        pass

    def noZstd(self) -> bool:
        "Return whether zstd compression is disabled"
        pass
