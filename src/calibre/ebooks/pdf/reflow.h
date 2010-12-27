/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 * Based on pdftohtml from the poppler project.
 */

#pragma once
#define UNICODE

#ifdef _WIN32 
#include <poppler/Object.h>
#elif defined(_OSX)
#include <poppler/Object.h>
#else
#include <Object.h>
#endif

#include <PDFDoc.h>
#include <GlobalParams.h>
#include <GfxState.h>
#include <GfxFont.h>
#include <OutputDev.h>
#include <Link.h>
#include <UnicodeMap.h>
#include <cmath>
#include <exception>
#include <string>
#include <sstream>
#include <vector>
#include <iostream>
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <map>
#include <errno.h>
#include "fonts.h"
#include "links.h"
#include "images.h"

using namespace std;

namespace calibre_reflow {


enum UnicodeTextDirection {
  text_dir_unknown,
  text_dir_left_right,
  text_dir_right_left,
  text_dir_top_bottom
};

class Reflow {

    private:
        char *pdfdata;
        double current_font_size;
        PDFDoc *doc;
        Object obj;

        string decode_info_string(Dict *info, const char *key) const;
        void outline_level(ostringstream *oss, GooList *items,
                            int level=1);

    public:
        Reflow (char *xpdfdata, size_t sz);
        ~Reflow();
        
        /* Convert the PDF to XML. All files are output to the current directory */
        void render();

        /* Get the PDF Info Dictionary */
        map<string, string> get_info();

        /* True if the PDF is encrypted */
        bool is_locked() const { return !this->doc || this->doc->isEncrypted(); }

        /* Return the first page of the PDF, rendered as a PNG image */
        vector<char>* render_first_page(bool use_crop_box=true, double x_res=150.0,
            double y_res = 150.0);

        /* Dump the PDF outline as the file outline.xml in the current directory */
        void dump_outline();

        /* Set the info dictionary. Currently broken. */
        string set_info(map<char *, char *> info);

        /* Number of pages in the document */
        int numpages() { return this->doc->getNumPages(); }
};

class XMLString {
    private:
        vector<Unicode> *text;  // the text
        vector<double> *x_right; // right-hand x coord of each char
        XMLString *yx_next;	    	// next string in y-major order
        XMLString *xy_next;		    // next string in x-major order
        Fonts *fonts;
        Fonts::size_type font_idx;
        string *xml_text;
        XMLLink *link;

        double x_min, x_max;		// bounding box x coordinates
        double y_min, y_max;		// bounding box y coordinates
        int col;		        	// starting column
        UnicodeTextDirection dir;	// direction (left to right/right to left)

        friend class XMLPage;

    public:
        XMLString(GfxState *state, GooString *s, double current_font_size, Fonts *fonts);
        ~XMLString();

        bool character_does_not_belong_to_string(GfxState *state, double x1) {
            return this->length() > 0 && 
                fabs(x1 - x_right->at(this->length()-1)) > 0.1 * (y_max - y_min);
        }
        
        void add_char(GfxState *state, double x, double y,
            	       double dx, double dy, Unicode u);

        void end_string();
        inline int length() const { return this->text->size(); }
        inline double height() const { return y_max - y_min; }
        void encode();
        XMLLink* get_link() { return this->link; }
        string str() const;
};

class XMLPage {
    private:
        XMLString *current_string;
        unsigned int num;
        ofstream *output;
        double current_font_size;
        XMLString *yx_strings;	// strings in y-major order
        XMLString *xy_strings;	// strings in x-major order
        XMLString *yx_cur1, *yx_cur2;	// cursors for yxStrings list
        Fonts *fonts;
        XMLLinks *links;
        void coalesce();

    public:
        XMLPage(unsigned int num, GfxState *state, ofstream *output, Fonts* fonts);
        ~XMLPage();

        void update_font(GfxState *state);

        void begin_string(GfxState *state, GooString *s) {
            this->current_string = new XMLString(state, s,
                    this->current_font_size, this->fonts);
        }
        
        void draw_char(GfxState *state, double x, double y,
                double dx, double dy,
                double originX, double originY,
                CharCode code, int nBytes, Unicode *u, int uLen);

        void end_string();

        void end();

        void add_link(XMLLink *t) { this->links->push_back(t); }

        unsigned int number() const { return this->num; }
};

class XMLOutputDev : public OutputDev {
  public:
    XMLOutputDev(PDFDoc *doc);
    virtual ~XMLOutputDev();
    //---- get info about output device

    // Does this device use upside-down coordinates?
    // (Upside-down means (0,0) is the top left corner of the page.)
    virtual GBool upsideDown() { return gTrue; }

    // Does this device use drawChar() or drawString()?
    virtual GBool useDrawChar() { return gTrue; }

    // Does this device use beginType3Char/endType3Char?  Otherwise,
    // text in Type 3 fonts will be drawn with drawChar/drawString.
    virtual GBool interpretType3Chars() { return gFalse; }

    // Does this device need non-text content?
    virtual GBool needNonText() { return gTrue; }

    //----- initialization and control

    virtual GBool checkPageSlice(Page *page, double hDPI, double vDPI,
                                int rotate, GBool useMediaBox, GBool crop,
                                int sliceX, int sliceY, int sliceW, int sliceH,
                                GBool printing, Catalog * catalogA,
                                GBool (* abortCheckCbk)(void *data) = NULL,
                                void * abortCheckCbkData = NULL)
    {
    this->catalog = catalogA;
    return gTrue;
    }


    // Start a page.
    virtual void startPage(int page_num, GfxState *state) {
        this->current_page = new XMLPage(page_num, state, this->output, this->fonts);
    }


    // End a page.
    virtual void endPage();

    //----- update text state
    virtual void updateFont(GfxState *state) {current_page->update_font(state);}

    //----- text drawing
    virtual void beginString(GfxState *state, GooString *s) {
        this->current_page->begin_string(state, s);
    }
    virtual void endString(GfxState *state) {
        this->current_page->end_string();
    }
    virtual void drawChar(GfxState *state, double x, double y,
                double dx, double dy,
                double originX, double originY,
                CharCode code, int nBytes, Unicode *u, int uLen) {
        this->current_page->draw_char(state, x, y, dx, dy, originX,
                originY, code, nBytes, u, uLen);
    }
    
    virtual void drawImageMask(GfxState *state, Object *ref, 
                    Stream *str,
                    int width, int height, GBool invert,
                    GBool interpolate, GBool inlineImg);
    virtual void drawImage(GfxState *state, Object *ref, Stream *str,
                int width, int height, GfxImageColorMap *colorMap,
                GBool interpolate, int *maskColors, GBool inlineImg);

    //new feature    
    virtual int DevType() {return 1234;}

  private:
    XMLPage *current_page;
    ofstream *output;                   // xml file
    Fonts *fonts;
    Catalog *catalog;
    XMLImages *images;
    PDFDoc *doc;

    void process_link(Link* link);
};
}
