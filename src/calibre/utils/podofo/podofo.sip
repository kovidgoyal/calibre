%Module podofo 0

%MappedType PdfString
{
%TypeHeaderCode
#define USING_SHARED_PODOFO
#include <PdfString.h>
using namespace PoDoFo;
%End
%ConvertFromTypeCode
		if (sipCpp -> IsValid()) {
            std::string raw = sipCpp->GetStringUtf8();
			return PyString_FromStringAndSize(raw.c_str(), raw.length());
		} else return PyString_FromString("");
%End
%ConvertToTypeCode
		if (sipIsErr == NULL) {
			if (sipIsErr == NULL)
    			return (PyUnicode_Check(sipPy) || PyString_Check(sipPy));
		}
         if (sipPy == Py_None) {
             *sipCppPtr = NULL;
             return 0;
         }
         if (PyString_Check(sipPy)) {
             *sipCppPtr = new PdfString((pdf_utf8 *)PyString_AS_STRING(sipPy));
			 return sipGetState(sipTransferObj);
		 }
		 if (PyUnicode_Check(sipPy)) {
             Py_UNICODE* u = PyUnicode_AS_UNICODE(sipPy);
             PyObject *u8 = PyUnicode_EncodeUTF8(u, PyUnicode_GET_SIZE(sipPy), "replace");
             pdf_utf8 *s8 = (pdf_utf8 *)PyString_AS_STRING(u8);
			 *sipCppPtr = new PdfString(s8);
			 return sipGetState(sipTransferObj);
		 }
		 *sipCppPtr = (PdfString *)sipForceConvertTo_PdfString(sipPy,sipIsErr);
         return 1;
%End
};

class PdfObject {
%TypeHeaderCode
#define USING_SHARED_PODOFO
#include <PdfObject.h>
using namespace PoDoFo;
%End
	public:
		PdfObject();

};

class PdfInfo {
%TypeHeaderCode
#define USING_SHARED_PODOFO
#include <PdfInfo.h>
using namespace PoDoFo;
%End
	public:
		PdfInfo(PdfObject *);
		
		PdfString GetAuthor() const;
		PdfString GetSubject() const;	
		PdfString GetTitle() const;
		PdfString GetKeywords() const;
        PdfString GetCreator() const;
        PdfString GetProducer() const;
		
		void SetAuthor(PdfString &);
		void SetSubject(PdfString &);
		void SetTitle(PdfString &);
		void SetKeywords(PdfString &);
        void SetCreator(PdfString &);
        void SetProducer(PdfString &);
	
};

class PdfOutputDevice {
%TypeHeaderCode
#define USING_SHARED_PODOFO
#include <PdfOutputDevice.h>
using namespace PoDoFo;
%End
	public:
		PdfOutputDevice(char *, long);
        unsigned long GetLength();
        unsigned long Tell();
        void Flush();
};


class PdfMemDocument {
%TypeHeaderCode
#define USING_SHARED_PODOFO
#include <PdfMemDocument.h>
using namespace PoDoFo;
%End
	public:
		PdfMemDocument();
		
		void Load(const char *filename);
        void Load(const char *buffer, long size);
		void Write(const char *filename);
		PdfInfo *GetInfo() const;

    protected:
        void SetInfo(PdfInfo * /TransferThis/);

    private:
        PdfMemDocument(PdfMemDocument &);
		
};


%Exception PoDoFo::PdfError  /PyName=PdfError/
{
%TypeHeaderCode
#define USING_SHARED_PODOFO
#include <PdfError.h>
%End
%RaiseCode
        const char *detail = sipExceptionRef.what();

        SIP_BLOCK_THREADS
        PyErr_SetString(sipException_PoDoFo_PdfError, detail);
        SIP_UNBLOCK_THREADS
%End
};

