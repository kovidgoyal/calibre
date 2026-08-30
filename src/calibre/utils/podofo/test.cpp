#define USING_SHARED_PODOFO
#include <podofo.h>
#include <iostream>

using namespace PoDoFo;
using namespace std;


int
main(int argc, char **argv) {
    if (argc < 2) return 1;
    char *fname = argv[1];

    PdfMemDocument doc;
    doc.Load(fname);
    auto &metadata = doc.GetMetadata();
    cout << endl;
    auto old_title = metadata.GetTitle();
    cout << "old title: " << (old_title.has_value() ? old_title->GetString() : "<none>") << endl;
    metadata.SetTitle(PdfString("zzz"));

    doc.Save("/t/x.pdf");
    cout << "Output written to: " << "/t/x.pdf" << endl;
    return 0;
}
