/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */

#include <Outline.h>
#include <PDFDocEncoding.h>
#include <poppler/ErrorCodes.h>
#include <goo/GooList.h>
#include <SplashOutputDev.h>
#include <splash/SplashBitmap.h>
#include <splash/SplashErrorCodes.h>
#include "reflow.h"
#include "utils.h"

using namespace std;
using namespace calibre_reflow;

static const size_t num_info_keys = 8;
static const char* info_keys[num_info_keys] = {
    "Title", "Subject", "Keywords", "Author", "Creator", "Producer",
    "CreationDate", "ModDate"
};
static char encoding[10] = "UTF-8";
static char yes[10] = "yes";


//------------------------------------------------------------------------
// XMLString
//------------------------------------------------------------------------

XMLString::XMLString(GfxState *state, GooString *s, double current_font_size,
        Fonts *fonts) : 
    text(new vector<Unicode>(0)), x_right(new vector<double>(0)),
    yx_next(NULL), xy_next(NULL), fonts(fonts), font_idx(0), xml_text(NULL),
    link(NULL), x_min(0), x_max(0), y_min(0), y_max(0), col(0), dir(text_dir_unknown)
{
    double x = 0, y = 0;
    GfxFont *font;

    state->transform(state->getCurX(), state->getCurY(), &x, &y);

    if ((font = state->getFont())) {
        double ascent = font->getAscent();
        double descent = font->getDescent();
        if( ascent > 1.05 ){
            //printf( "ascent=%.15g is too high, descent=%.15g\n", ascent, descent );
            ascent = 1.05;
        }
        if( descent < -0.4 ){
            //printf( "descent %.15g is too low, ascent=%.15g\n", descent, ascent );
            descent = -0.4;
        }
        this->y_min = y - ascent * current_font_size;
        this->y_max = y - descent * current_font_size;
        GfxRGB rgb;
        state->getFillRGB(&rgb);
        GooString *name = state->getFont()->getName();
        if (!name)
            this->font_idx = this->fonts->add_font(NULL, current_font_size-1, rgb);
        else
            this->font_idx = this->fonts->add_font(
                    new string(name->getCString()), current_font_size-1, rgb);

    } else {
        // this means that the PDF file draws text without a current font,
        // which should never happen
        this->y_min = y - 0.95 * current_font_size;
        this->y_max = y + 0.35 * current_font_size;
    }
    if (this->y_min == this->y_max) {
        // this is a sanity check for a case that shouldn't happen -- but
        // if it does happen, we want to avoid dividing by zero later
        this->y_min = y;
        this->y_max = y + 1;
    }
}

void XMLString::add_char(GfxState *state, double x, double y,
            	       double dx, double dy, Unicode u) {
    if (dir == text_dir_unknown) {
        //dir = UnicodeMap::getDirection(u);
        dir = text_dir_left_right;
    } 

    if (this->text->capacity() == this->text->size()) {
        this->text->reserve(text->size()+16);
        this->x_right->reserve(x_right->size()+16);
    }
    this->text->push_back(u);
    if (this->length() == 1) {
        this->x_min = x;
    }
    this->x_max = x + dx;
    this->x_right->push_back(x_max);
    //printf("added char: %f %f xright = %f\n", x, dx, x+dx);
}

void XMLString::end_string()
{
    if( this->dir == text_dir_right_left && this->length() > 1 )
    {
        //printf("will reverse!\n");
        reverse(this->text->begin(), this->text->end());
    }
}

static string encode_unicode_chars(const Unicode *u, size_t num) {
    ostringstream oss;
    UnicodeMap *uMap;
    char buf[10];
    int n;
    if (!(uMap = globalParams->getTextEncoding())) {
        throw ReflowException("Failed to allocate unicode map.");
    }

    for (size_t i = 0; i < num; i++) {
        switch (u[i]) {
            case '&': oss << "&amp;";  break;
        	case '<': oss << "&lt;";  break;
        	case '>': oss << "&gt;";  break;
        	default:  
	        {
                // convert unicode to string
                if ((n = uMap->mapUnicode(u[i], buf, sizeof(buf))) > 0) {
                    buf[n] = 0;
                    oss << buf;
                }
            }
        }
    }
    uMap->decRefCnt();
    return oss.str();
}

void XMLString::encode() {
    delete this->xml_text;
    this->xml_text = new string(encode_unicode_chars(&((*this->text)[0]), this->text->size()));
}

string XMLString::str() const {
        ostringstream oss;
        oss << "<text font=\"" << this->font_idx << "\" ";
        oss << setiosflags(ios::fixed) << setprecision(2)
            << "top=\"" << this->y_min << "\" left=\"" << this->x_min
            << "\" width=\"" << this->x_max - this->x_min << "\" "
            << "height=\"" << this->y_max - this->y_min << "\">";
        oss << *this->xml_text << "</text>";
        return oss.str();
}

XMLString::~XMLString() {
    delete this->text; delete this->x_right; delete this->xml_text;
}


//------------------------------------------------------------------------
// XMLPage
//------------------------------------------------------------------------

XMLPage::XMLPage(unsigned int num, GfxState *state, ofstream *output, Fonts* fonts) :
    current_string(NULL), num(num), output(output), current_font_size(0.0),
    yx_strings(NULL), xy_strings(NULL), yx_cur1(NULL), yx_cur2(NULL),
    fonts(fonts), links(new XMLLinks())
{
    (*this->output) << setiosflags(ios::fixed) << setprecision(2) <<
        "\t\t<page number=\"" << this->num << "\" width=\"" <<        
        state->getPageWidth() << "\" height=\"" << state->getPageHeight() <<
        "\">" << endl;
    if (!(*this->output)) throw ReflowException(strerror(errno));
}

XMLPage::~XMLPage() {
   (*this->output) << "\t\t</page>" << endl;
   if (!(*this->output)) throw ReflowException(strerror(errno));
   for (XMLString *tmp = this->yx_strings; tmp; tmp = tmp->yx_next)
       delete tmp;

   delete this->links;
}

void XMLPage::update_font(GfxState *state) {
    GfxFont *font;
    double *fm;
    char *name;
    int code;
    double w;

    current_font_size = state->getTransformedFontSize();

    if ((font = state->getFont()) && font->getType() == fontType3) {
        // This is a hack which makes it possible to deal with some Type 3
        // fonts.  The problem is that it's impossible to know what the
        // base coordinate system used in the font is without actually
        // rendering the font.  This code tries to guess by looking at the
        // width of the character 'm' (which breaks if the font is a
        // subset that doesn't contain 'm').
        for (code = 0; code < 256; ++code) {
            if ((name = ((Gfx8BitFont *)font)->getCharName(code)) &&
                name[0] == 'm' && name[1] == '\0')  break;
            
        }
        if (code < 256) {
            w = ((Gfx8BitFont *)font)->getWidth(code);
            if (w != 0) {
                // 600 is a generic average 'm' width -- yes, this is a hack
                current_font_size *= w / 0.6;
            }
        }
        fm = font->getFontMatrix();
        if (fm[0] != 0) {
            current_font_size *= fabs(fm[3] / fm[0]);
        }
    }

}

void XMLPage::draw_char(GfxState *state, double x, double y,
                double dx, double dy,
                double originX, double originY,
                CharCode code, int nBytes, Unicode *u, int uLen) {
    if ( (state->getRender() & 3) == 3)  return; //Hidden text
    double x1, y1, w1, h1, dx2, dy2;
    int i;
    state->transform(x, y, &x1, &y1);
    
    // check that new character is in the same direction as current string
    // and is not too far away from it before adding 
    if (this->current_string->character_does_not_belong_to_string(state, x1)) {
        this->end_string();
        this->begin_string(state, NULL);
    }
    state->textTransformDelta(state->getCharSpace() * state->getHorizScaling(),
                    0, &dx2, &dy2);
    dx -= dx2;
    dy -= dy2;
    state->transformDelta(dx, dy, &w1, &h1);
    if (uLen != 0) {
        w1 /= uLen;
        h1 /= uLen;
    }
    for (i = 0; i < uLen; ++i) {
        this->current_string->add_char(state, x1 + i*w1, y1 + i*h1, w1, h1, u[i]);
    }

}

void XMLPage::end_string() {
  XMLString *p1 = NULL, *p2 = NULL;
  double h, y1, y2;

  // throw away zero-length strings -- they don't have valid xMin/xMax
  // values, and they're useless anyway
  if (this->current_string->length() == 0) {
    delete this->current_string;
    this->current_string = NULL;
    return;
  }

  this->current_string->end_string();

  // insert string in y-major list
  h = this->current_string->height();
  y1 = this->current_string->y_min + 0.5 * h;
  y2 = this->current_string->y_min + 0.8 * h;
  if (gFalse) { //rawOrder
    p1 = this->yx_cur1;
    p2 = NULL;
  } else if (
          (!this->yx_cur1 ||
              (y1 >= this->yx_cur1->y_min &&
               (y2 >= this->yx_cur1->y_max ||
                this->current_string->x_max >= this->yx_cur1->x_min))) &&
             (!this->yx_cur2 ||
              (y1 < this->yx_cur2->y_min ||
               (y2 < this->yx_cur2->y_max &&
                this->current_string->x_max < this->yx_cur2->x_min)))
             ) {
    p1 = this->yx_cur1;
    p2 = this->yx_cur2;
  } else {
    for (p1 = NULL, p2 = this->yx_strings; p2; p1 = p2, p2 = p2->yx_next) {
      if (y1 < p2->y_min || (y2 < p2->y_max && this->current_string->x_max < p2->x_min))
        break;
    }
    this->yx_cur2 = p2;
  }
  this->yx_cur1 = this->current_string;
  if (p1)
    p1->yx_next = this->current_string;
  else
    this->yx_strings = this->current_string;
  this->current_string->yx_next = p2;
  this->current_string = NULL;
}

void XMLPage::end() {
  XMLLinks::size_type link_index = 0;
  Fonts::size_type pos = 0;
  XMLFont* h;

  for (XMLString *tmp = this->yx_strings; tmp; tmp = tmp->yx_next) {
     pos = tmp->font_idx;
     h = this->fonts->at(pos);

     tmp->encode();

     if (this->links->in_link(
            tmp->x_min, tmp->y_min, tmp->x_max, tmp->y_max, link_index)) {
       tmp->link = links->at(link_index);
     }
  }

  this->coalesce();

  for (XMLString *tmp = yx_strings; tmp; tmp=tmp->yx_next) {
    if (tmp->xml_text && tmp->xml_text->size() > 0) {
        (*this->output) << "\t\t\t" << tmp->str() << endl;
        if (!(*this->output)) throw ReflowException(strerror(errno));
    }
  }
}

static const char *strrstr( const char *s, const char *ss )
{
  const char *p = strstr( s, ss );
  for( const char *pp = p; pp != NULL; pp = strstr( p+1, ss ) ){
    p = pp;
  }
  return p;
}


static void close_tags( string *xml_text, bool &finish_a, bool &finish_italic, bool &finish_bold )
{
  const char *last_italic = finish_italic && ( finish_bold   || finish_a    ) ? strrstr( xml_text->c_str(), "<em>" ) : NULL;
  const char *last_bold   = finish_bold   && ( finish_italic || finish_a    ) ? strrstr( xml_text->c_str(), "<strong>" ) : NULL;
  const char *last_a      = finish_a      && ( finish_italic || finish_bold ) ? strrstr( xml_text->c_str(), "<a " ) : NULL;
  if( finish_a && ( finish_italic || finish_bold ) && last_a > ( last_italic > last_bold ? last_italic : last_bold ) ) {
    xml_text->append("</a>");
    finish_a = false;
  }
  if( finish_italic && finish_bold && last_italic > last_bold ){
    xml_text->append("</em>");
    finish_italic = false;
  }
  if( finish_bold )
    xml_text->append("</strong>");
  if( finish_italic )
    xml_text->append("</em>");
  if( finish_a )
    xml_text->append("</a>");
}

void XMLPage::coalesce() {
    XMLString *str1, *str2, *str3;
    XMLFont *hfont1, *hfont2;
    double space, hor_space, vert_space, vert_overlap, size, x_limit;
    bool add_space, found;
    int n, i;
    double cur_x, cur_y;

    str1 = this->yx_strings;

    if( !str1 ) return;

    //----- discard duplicated text (fake boldface, drop shadows)
  
  	while (str1)
	{
		size = str1->y_max - str1->y_min;
		x_limit = str1->x_min + size * 0.2;
		found = false;
		for (str2 = str1, str3 = str1->yx_next;
			str3 && str3->x_min < x_limit;
			str2 = str3, str3 = str2->yx_next)
		{
			if (str3->length() == str1->length() &&
				!memcmp(str3->text, str1->text, str1->length() * sizeof(Unicode)) &&
				fabs(str3->y_min - str1->y_min) < size * 0.2 &&
				fabs(str3->y_max - str1->y_max) < size * 0.2 &&
				fabs(str3->x_max - str1->x_max) < size * 0.2)
			{
				found = true;
				//printf("found duplicate!\n");
				break;
			}
		}
		if (found)
		{
			str2->xy_next = str3->xy_next;
			str2->yx_next = str3->yx_next;
			delete str3;
		}
		else
		{
			str1 = str1->yx_next;
		}
  }		
  
  str1 = yx_strings;
  
  hfont1 = this->fonts->at(str1->font_idx);
  if( hfont1->is_bold() )
    str1->xml_text->insert(0, "<strong>");
  if( hfont1->is_italic() )
    str1->xml_text->insert(0, "<em>");
  if (str1->get_link())
      str1->xml_text->insert(0, str1->get_link()->get_link_start());
  cur_x = str1->x_min; cur_y = str1->y_min;

  while (str1 && (str2 = str1->yx_next)) {
    hfont2 = this->fonts->at(str2->font_idx);
    space = str1->y_max - str1->y_min;
    hor_space = str2->x_min - str1->x_max;
    vert_space = str2->y_min - str1->y_max;

    vert_overlap = 0;
    if (str2->y_min >= str1->y_min && str2->y_min <= str1->y_max)
    {
        vert_overlap = str1->y_max - str2->y_min;
    } else if (str2->y_max >= str1->y_min && str2->y_max <= str1->y_max)
    {
        vert_overlap = str2->y_max - str1->y_min;
    }     
    if (
	(
	 (
	   (str2->y_min < str1->y_max) 
	   &&
	  (hor_space > -0.5 * space && hor_space < space)
	 ) 
	) &&
	(hfont1->eq_upto_inline(*hfont2)) && 
	str1->dir == str2->dir // text direction the same
       ) 
    {
      n = str1->length() + str2->length();
      if ((add_space = hor_space > 0.1 * space)) {
        ++n;
      }
  
      str1->text->reserve((n + 15) & ~15);
      str1->x_right->reserve((n + 15) & ~15);
      if (add_space) {
		  str1->text->push_back(0x20);
		  str1->xml_text->push_back(' ');
		  str1->x_right->push_back(str2->x_min);
      }
      
      for (i = 0; i < str2->length(); i++) {
    	str1->text->push_back(str2->text->at(i));
	    str1->x_right->push_back(str2->x_right->at(i));
      }

      /* fix <i>, <b> if str1 and str2 differ and handle switch of links */
      XMLLink *hlink1 = str1->get_link();
      XMLLink *hlink2 = str2->get_link();
      bool switch_links = !hlink1 || !hlink2 || !((*hlink1) == (*hlink2));
      bool finish_a = switch_links && hlink1 != NULL;
      bool finish_italic = hfont1->is_italic() && ( !hfont2->is_italic() || finish_a );
      bool finish_bold   = hfont1->is_bold()   && 
          ( !hfont2->is_bold()   || finish_a || finish_italic );
      close_tags( str1->xml_text, finish_a, finish_italic, finish_bold );
      if( switch_links && hlink2 != NULL ) {
        string ls = hlink2->get_link_start();
        str1->xml_text->append(ls);
      }
      if( ( !hfont1->is_italic() || finish_italic ) && hfont2->is_italic() )
	    str1->xml_text->append("<em>");
      if( ( !hfont1->is_bold() || finish_bold ) && hfont2->is_bold() )
	    str1->xml_text->append("<strong>");


      str1->xml_text->append(*str2->xml_text);
      // str1 now contains href for link of str2 (if it is defined)
      str1->link = str2->link; 
      hfont1 = hfont2;
      if (str2->x_max > str1->x_max) {
    	str1->x_max = str2->x_max;
      }
      if (str2->y_max > str1->y_max) {
    	str1->y_max = str2->y_max;
      }
      str1->yx_next = str2->yx_next;
      delete str2;
    } else { // keep strings separate
      bool finish_a = str1->get_link() != NULL;
      bool finish_bold   = hfont1->is_bold();
      bool finish_italic = hfont1->is_italic();
      close_tags( str1->xml_text, finish_a, finish_italic, finish_bold );
     
      str1->x_min = cur_x; str1->y_min = cur_y; 
      str1 = str2;
      cur_x = str1->x_min; cur_y = str1->y_min;
      hfont1 = hfont2;
      if ( hfont1->is_bold() )
    	str1->xml_text->insert(0, "<strong>");
      if( hfont1->is_italic() )
    	str1->xml_text->insert(0, "<em>");
      if( str1->get_link() != NULL ) {
	    str1->xml_text->insert(0, str1->get_link()->get_link_start());
      }
    }
  }
  str1->x_min = cur_x; str1->y_min = cur_y;

  bool finish_bold   = hfont1->is_bold();
  bool finish_italic = hfont1->is_italic();
  bool finish_a = str1->get_link() != NULL;
  close_tags( str1->xml_text, finish_a, finish_italic, finish_bold );

}


//------------------------------------------------------------------------
// XMLOutputDev
//------------------------------------------------------------------------

XMLOutputDev::XMLOutputDev(PDFDoc *doc) : 
    current_page(NULL), output(new ofstream("index.xml", ios::trunc)),
    fonts(new Fonts()), catalog(NULL), images(new XMLImages()), doc(doc)
{
    if (!(*this->output)) {
        throw ReflowException(strerror(errno));
    }
    (*this->output) << "<pdfreflow>" << endl;
    (*this->output) << "\t<pages>" << endl;
    if (!(*this->output)) throw ReflowException(strerror(errno));
}

XMLOutputDev::~XMLOutputDev() {
    (*this->output) << "\t</pages>" << endl;
    if (!(*this->output)) throw ReflowException(strerror(errno));
    (*this->output) << "\t<fonts>" << endl;
    if (!(*this->output)) throw ReflowException(strerror(errno));
    for (Fonts::const_iterator it = this->fonts->begin(); it < this->fonts->end(); it++) {
        (*this->output) << "\t\t" << (*it)->str(it - this->fonts->begin()) << endl;
        if (!(*this->output)) throw ReflowException(strerror(errno));
    }
    (*this->output) << "\t</fonts>" << endl;
    if (!(*this->output)) throw ReflowException(strerror(errno));
    (*this->output) << "</pdfreflow>" << endl;
    if (!(*this->output)) throw ReflowException(strerror(errno));
    this->output->close();
    delete this->output;
    delete this->fonts;
    delete this->images;
}

static string get_link_dest(LinkAction *link, PDFDoc *doc) {
  unsigned int page = 1;
  ostringstream oss;

  switch(link->getKind()) 
  {
      case actionGoTo:
	  { 
        LinkGoTo *ha = (LinkGoTo *)link;
        LinkDest *dest = NULL;
        if (ha->getDest() != NULL)
            dest = ha->getDest()->copy();
        else if (ha->getNamedDest() != NULL) {
            dest = doc->findDest(ha->getNamedDest());
        }
            
        if (dest) { 
            if (dest->isPageRef()) {
                Ref pageref = dest->getPageRef();
                page = doc->findPage(pageref.num, pageref.gen);
            }
            else {
                page = dest->getPageNum();
            }

            oss << "#" << page
                << setiosflags(ios::fixed) << setprecision(2)
                << ":l=" << dest->getLeft() 
                << "t=" << dest->getTop();
                //<< "r=" << dest->getRight()
                //<< "b=" << dest->getBottom();
            delete dest;
        }
        break;
	  }

      case actionGoToR:
	  {
        LinkGoToR *ha = (LinkGoToR *) link;
        LinkDest *dest = NULL;
        bool has_file = false;
        if (ha->getFileName()) {
            oss << ha->getFileName()->getCString();
            has_file = true;
        }
        if (ha->getDest() != NULL) dest=ha->getDest()->copy();

        if (dest && has_file) {
            if (!(dest->isPageRef()))  page = dest->getPageNum();
            delete dest;
            oss << '#' << page;
        }
        break;
      }
      case actionURI:
        { 
        LinkURI *ha=(LinkURI *) link;
        oss << ha->getURI()->getCString();
        break;
      }
      case actionLaunch:
      {
        LinkLaunch *ha = (LinkLaunch *) link;
        oss << ha->getFileName()->getCString();
        break;
	  }
      case actionNamed: break;
      case actionMovie: break;
      case actionRendition: break;
      case actionSound: break;
      case actionJavaScript: break;
      case actionUnknown: break;
      default: break;
  }
  return oss.str();
}

void XMLOutputDev::process_link(AnnotLink* link){

  double _x1, _y1, _x2, _y2;
  int x1, y1, x2, y2;
  
  link->getRect(&_x1, &_y1, &_x2, &_y2);
  cvtUserToDev(_x1, _y1, &x1, &y1);
  
  cvtUserToDev(_x2, _y2, &x2, &y2); 

  LinkAction *a = link->getAction();
  if (!a) return;
  string dest = get_link_dest(a, this->doc);
  if (dest.length() > 0) {
      XMLLink *t = new XMLLink((double)x1, (double)y2, (double)x2, (double)y1,
              dest.c_str());
      this->current_page->add_link(t); 
  }
}


void XMLOutputDev::endPage() {
#ifdef POPPLER_PRE_20
    Links *slinks = catalog->getPage(current_page->number())->getLinks(catalog);
#else
    Links *slinks = catalog->getPage(current_page->number())->getLinks();
#endif

    for (int i = 0; i < slinks->getNumLinks(); i++)
    {
        this->process_link(slinks->getLink(i));
    }
    delete slinks;
    
    this->current_page->end();
    vector<string*> images = this->images->str();
    for (vector<string*>::iterator it = images.begin(); it < images.end(); it++) {
        (*this->output) << "\t\t\t" << *(*it) << endl;
        if (!(*this->output)) throw ReflowException(strerror(errno));
        delete *it;
    }
    this->images->clear();
    delete this->current_page;
    this->current_page = NULL;
}


void XMLOutputDev::drawImageMask(GfxState *state, Object *ref, Stream *str,
				  int width, int height, GBool invert,
				  GBool interpolate, GBool inlineImg) {
    OutputDev::drawImageMask(state, ref, str, width, height,
            invert, interpolate, inlineImg);
    //this->images->add_mask();
    cerr << "mask requested" << endl;
}

void XMLOutputDev::drawImage(GfxState *state, Object *ref, Stream *str,
			      int width, int height, GfxImageColorMap *colorMap,
			      GBool interpolate, int *maskColors, GBool inlineImg) {
    this->images->add(state, ref, str,
            static_cast<unsigned int>(width), static_cast<unsigned int>(height),
            colorMap, interpolate, maskColors, inlineImg);
}

Reflow::Reflow(char *pdfdata, size_t sz) :
    pdfdata(pdfdata), current_font_size(-1), doc(NULL), obj()
{
    int err;
    this->obj.initNull();
    if (globalParams == NULL) {
        globalParams = new GlobalParams();
        if (!globalParams)
            throw ReflowException("Failed to allocate Globalparams");
    }
    MemStream *str = new MemStream(pdfdata, 0, sz, &this->obj);
    this->doc = new PDFDoc(str, NULL, NULL);

    if (!this->doc->isOk()) {
        err = this->doc->getErrorCode();
        ostringstream stm;
        if (err == errEncrypted) 
            stm << "PDF is password protected.";
        else {
            stm << "Failed to open PDF file";
            stm << " with error code: " << err;
        }
        delete this->doc;
        this->doc = NULL;
        throw ReflowException(stm.str().c_str());
    }

}

int
Reflow::render(int first_page, int last_page) {

    if (!this->doc->okToCopy()) 
        cout << "Warning, this document has the copy protection flag set, ignoring." << endl;

    globalParams->setTextEncoding(encoding);

    int doc_pages = doc->getNumPages();
    if (last_page < 1 || last_page > doc_pages) last_page = doc_pages;
    if (first_page < 1) first_page = 1;
    if (first_page > last_page) first_page = last_page;

    XMLOutputDev *xml_out = new XMLOutputDev(this->doc);
    doc->displayPages(xml_out, first_page, last_page,
              96, //hDPI
              96, //vDPI
              0, //rotate
		      true, //UseMediaBox
              true, //Crop
              false //Printing
    );
    
    if (last_page - first_page == doc_pages - 1)
        this->dump_outline();

    delete xml_out;

    return doc_pages;
}

void Reflow::dump_outline() {
	Outline *outline = this->doc->getOutline();
    if (!outline) return;
    GooList *items = outline->getItems();
    if ( !items || items->getLength() < 1 )
        return;

    ostringstream *output = new ostringstream();
    (*output) << "<outline>" << endl;
    this->outline_level(output, items);
    (*output) << "</outline>" << endl;
    ofstream of("outline.xml", ios::trunc);
    of << output->str();
    if (!of) throw ReflowException("Error writing outline file");
    of.close();
    delete output;
}

static inline void outline_tabs(ostringstream *o, int level) {
    for (int i = 0; i < level; i++)
        (*o) << "\t";
}

void Reflow::outline_level(ostringstream *oss, GooList *items, int level)
{
    int num_of_items = items->getLength();
    if (num_of_items > 0) {
        outline_tabs(oss, level);
        (*oss) << "<links level=\"" << level << "\">" << endl;

        for (int i = 0; i < num_of_items; i++) {
            OutlineItem* item = (OutlineItem *)items->get(i);
            Unicode *u = item->getTitle();
            string title = encode_unicode_chars(u, item->getTitleLength());
            if (title.size() < 1) continue;
            outline_tabs(oss, level+1);
            (*oss) << "<link open=\"" << (item->isOpen()?"yes":"no") << "\"";
            LinkAction *a = item->getAction();
            if (a != NULL)
                (*oss) << " dest=\"" << get_link_dest(a, this->doc) << "\"";
            (*oss) << ">" << title << "</link>" << endl;
            item->open();
            GooList *children = item->getKids();
            if (children)
                outline_level(oss, children, level+1);
        }
    }
}

Reflow::~Reflow() {
    delete this->doc;
}

map<string, string> Reflow::get_info() {
    Object info;
    map<string, string> ans;
    string val;
    globalParams->setTextEncoding(encoding);

    this->doc->getDocInfo(&info);
    if (info.isDict()) {
        for(size_t i = 0; i < num_info_keys; i++) {
            val = this->decode_info_string(info.getDict(), info_keys[i]);
            if (val.size() > 0) {
                ans[string(info_keys[i])] = string(val);
            }
        }
    }
    return ans;
}

string Reflow::decode_info_string(Dict *info, const char *key) const {
    Object obj;
    GooString *s1;
    bool is_unicode;
    Unicode u;
    char buf[8];
    int i, n;
    ostringstream oss;
    char *tmp = new char[strlen(key)+1];
    strncpy(tmp, key, strlen(key)+1);
    UnicodeMap *umap;
    if (!(umap = globalParams->getTextEncoding())) {
        throw ReflowException("Failed to allocate unicode map.");
    }


    if (info->lookup(tmp, &obj)->isString()) {
        s1 = obj.getString();
        if ((s1->getChar(0) & 0xff) == 0xfe &&
        (s1->getChar(1) & 0xff) == 0xff) {
            is_unicode = true;
            i = 2;
        } else {
            is_unicode = false;
            i = 0;
        }
        while (i < obj.getString()->getLength()) {
            if (is_unicode) {
                u = ((s1->getChar(i) & 0xff) << 8) |
                (s1->getChar(i+1) & 0xff);
                i += 2;
            } else {
                u = pdfDocEncoding[s1->getChar(i) & 0xff];
                ++i;
            }
            n = umap->mapUnicode(u, buf, sizeof(buf));
            buf[n] = 0;
            oss << buf;
        }
    }
    obj.free();
    delete[] tmp;
    return oss.str();
}

vector<char>* Reflow::render_first_page(bool use_crop_box, double x_res,
        double y_res) {
    if (this->numpages() < 1) throw ReflowException("Document has no pages.");
    globalParams->setTextEncoding(encoding);
    globalParams->setEnableFreeType(yes);
    globalParams->setAntialias(yes);
    globalParams->setVectorAntialias(yes);
    
    SplashColor paper_color;
    paper_color[0] = 255;
    paper_color[1] = 255;
    paper_color[2] = 255;
    SplashOutputDev *out = new SplashOutputDev(splashModeRGB8, 4, false, paper_color, true, true);
    out->setVectorAntialias(true);
    if (!out) {
        throw ReflowException("Failed to allocate SplashOutputDev");
    }
    try {
#ifdef POPPLER_PRE_20
        out->startDoc(doc->getXRef());
#else
        out->startDoc(doc);
#endif
        out->startPage(1, NULL);

        double pg_w, pg_h;
        int pg = 1;

        if (use_crop_box) {
            pg_w = this->doc->getPageCropWidth(pg);
            pg_h = this->doc->getPageCropHeight(pg);
        } else {
            pg_w = this->doc->getPageMediaWidth(pg);
            pg_h = this->doc->getPageMediaHeight(pg);
        }

        pg_w *= x_res/72.;
        pg_h *= y_res/72.;

        int x=0, y=0;
        this->doc->displayPageSlice(out, pg, x_res, y_res, 0,
                !use_crop_box, false, false, x, y, pg_w, pg_h);
    } catch(...) { delete out; throw; }

    SplashBitmap *bmp = out->takeBitmap();
    out->endPage();
    delete out; out = NULL;
    PNGMemWriter writer;
    vector<char> *buf = new vector<char>();
    try {
        writer.init(buf, bmp->getWidth(), bmp->getHeight()); 
        writer.write_splash_bitmap(bmp);
        writer.close();
    } catch(...) { delete buf; delete bmp; throw; }
    delete bmp;
    return buf;
}

class MemOutStream : public OutStream {
    private:
        ostringstream out;

    public:
        MemOutStream() :OutStream() {}
        ~MemOutStream() {}
        void close() {}
        int getPos() { return out.tellp(); }
        void put(char c) { out.put(c); }
        void printf (const char *format, ...) {
            vector<char> buf;
            size_t written = strlen(format)*5;
            va_list ap;
            do {
                buf.reserve(written + 20);
                va_start(ap, format);
                written = vsnprintf(&buf[0], buf.capacity(), format, ap);
                va_end(ap);
            } while (written >= buf.capacity());
            out.write(&buf[0], written);            
        }
};

string Reflow::set_info(map<char *, char *> sinfo) {
    XRef *xref = this->doc->getXRef();
    if (!xref) throw ReflowException("No XRef table");
    Object *trailer_dict = xref->getTrailerDict();
    if (!trailer_dict || !trailer_dict->isDict()) throw ReflowException("No trailer dictionary");
    Object tmp;
    char INFO[5] = "Info";
    Object *info = trailer_dict->dictLookup(INFO, &tmp);
    if (!info) {
        info = new Object();
        info->initDict(xref);
    }
    if (!info->isDict()) throw ReflowException("Invalid info object");

    for (map<char *, char *>::iterator it = sinfo.begin(); it != sinfo.end(); it++) {
        Object *tmp = new Object();
        tmp->initString(new GooString((*it).second));
        info->dictSet((*it).first, tmp);
    }

    trailer_dict->dictSet(INFO, info);
    char out[20] = "/t/out.pdf";
    this->doc->saveAs(new GooString(out), writeForceRewrite);
    string ans;
    return ans;
}

