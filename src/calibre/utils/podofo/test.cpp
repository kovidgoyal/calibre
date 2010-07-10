#define USING_SHARED_PODOFO
#include <podofo.h>
#include <iostream>

using namespace PoDoFo;
using namespace std;


int main(int argc, char **argv) {
    if (argc < 2) return 1;
    char *fname = argv[1];

    PdfMemDocument doc(fname);
    PdfInfo* info = doc.GetInfo();
    cout << endl;
    cout << "is encrypted: " << doc.GetEncrypted() << endl;
    PdfString old_title = info->GetTitle();
    cout << "is hex: " << old_title.IsHex() << endl; 
    PdfString new_title(reinterpret_cast<const pdf_utf16be*>("\0z\0z\0z"), 3);
    cout << "is new unicode: " << new_title.IsUnicode() << endl;
    info->SetTitle(new_title);

    doc.Write("/t/x.pdf");
    cout << "Output written to: " << "/t/x.pdf" << endl;
    return 0;
}
