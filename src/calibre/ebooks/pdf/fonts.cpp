/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */



#include "fonts.h"
#include "utils.h"

using namespace calibre_reflow;
using namespace std;

XMLColor::XMLColor(GfxRGB rgb) {
  this->r = static_cast<int>(rgb.r/65535.0*255.0);
  this->g = static_cast<int>(rgb.g/65535.0*255.0);
  this->b = static_cast<int>(rgb.b/65535.0*255.0);
  if (!(this->ok(this->r) && this->ok(this->b) && this->ok(this->g))) {
    this->r = 0; this->g = 0; this->b = 0;
  }
}

string XMLColor::str() const {
    ostringstream oss;
    oss << "rgb(" << this->r << "," << this->g << "," << this->b << ")";
    return oss.str();
}

static const char *FONT_MODS[7] = {
    "-bolditalic", "-boldoblique", "-bold", "-italic", "-oblique", "-roman",
    NULL
};

#ifdef _WIN32
#define ap_toupper(c) (toupper(((unsigned char)(c))))
static inline
const char *strcasestr(const char *h, const char *n )
{ /* h="haystack", n="needle" */
    const char *a=h, *e=n;

    if( !h || !*h || !n || !*n ) { return 0; }

    while( *a && *e ) {
        if( ap_toupper(*a)!=ap_toupper(*e) ) {
            ++h; a=h; e=n;
        }
        else {
            ++a; ++e;
        }
    }
    return *e ? 0 : h;
}
#endif

static string* family_name(const string *font_name) {
    if (!font_name) return NULL;
    string *fn = new string(*font_name);
    size_t pos;
    const char *p;
    for (size_t i = 0; FONT_MODS[i] != NULL; i++) {
        p = strcasestr(fn->c_str(), FONT_MODS[i]);
        if (p != NULL) {
            pos = p - fn->c_str();
            fn->replace(pos, strlen(FONT_MODS[i]), "");
            break;
        }
    }
    return fn;
}

XMLFont::XMLFont(string* font_name, double size, GfxRGB rgb) :
        size(size-1), line_size(-1.0), italic(false), bold(false), font_name(font_name),
        font_family(NULL), color(rgb)  {

    if (!this->font_name) this->font_name = new string(DEFAULT_FONT_FAMILY);
    this->font_family = family_name(this->font_name);
    if (strcasestr(font_name->c_str(), "bold")) this->bold = true;

    if (strcasestr(font_name->c_str(),"italic")||
        strcasestr(font_name->c_str(),"oblique")) this->italic = true;


}

XMLFont& XMLFont::operator=(const XMLFont& x){
   if (this==&x) return *this; 
   this->size = x.size;
   this->line_size = x.line_size;
   this->italic = x.italic;
   this->bold = x.bold;
   this->color = x.color;
   if (this->font_name) delete this->font_name;
   this->font_name = new string(*x.font_name);
   if (this->font_family) delete this->font_family;
   this->font_family = new string(*x.font_family);
   return *this;
}

bool XMLFont::operator==(const XMLFont &f) const {
    return (fabs(this->size - f.size) < 0.1) && 
        (fabs(this->line_size - f.line_size) < 0.1) &&
        (this->italic == f.italic) &&
        (this->bold == f.bold) &&
        (this->color == f.color) &&
        ((*this->font_family) == (*f.font_family));
}

bool XMLFont::eq_upto_inline(const XMLFont &f) const {
    return (fabs(this->size - f.size) < 0.1) && 
        (fabs(this->line_size - f.line_size) < 0.1) &&
        (this->color == f.color) &&
        ((*this->font_family) == (*f.font_family));
}

string XMLFont::str(Fonts::size_type id) const {
    ostringstream oss;
    oss << "<font id=\"" << id << "\" ";
    oss << "family=\"" << encode_for_xml(*this->font_family) << "\" ";
    oss << "color=\"" << this->color.str() << "\" ";
    oss << setiosflags(ios::fixed) << setprecision(2) 
        << "size=\"" << this->size << "\"";
    oss << "/>";
    return oss.str();
}

Fonts::size_type Fonts::add_font(XMLFont *f) {
    Fonts::iterator it;
    size_type i;
    for ( i=0, it=this->begin(); it < this->end(); it++, i++ ) {
        if (**it == *f) return i;
    }
    this->push_back(f);
    return this->size()-1;
}

Fonts::size_type Fonts::add_font(string* font_name, double size, GfxRGB rgb) {
    XMLFont *f = new XMLFont(font_name, size, rgb);
    return this->add_font(f);
}

Fonts::~Fonts() {
    Fonts::iterator it;
    for ( it=this->begin(); it < this->end(); it++ ) delete *it;
    this->resize(0);
}
