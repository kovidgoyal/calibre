/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */


#pragma once

#include <vector>
#include <sstream>
#include <iomanip>
#include <ctype.h>
#include <math.h>
#include <GfxState.h>

using namespace std;

#define DEFAULT_FONT_FAMILY "Times New Roman"

namespace calibre_reflow {

class XMLColor {

 private:
   unsigned int r;
   unsigned int g;
   unsigned int b;
   inline bool ok(unsigned int xcol) const { 
       return ( (xcol <= 255) && (xcol >= 0) );
   }

 public:
   XMLColor():r(0),g(0),b(0){}

   XMLColor(GfxRGB rgb);
   
   XMLColor(const XMLColor& x) {
       this->r=x.r; this->g=x.g; this->b=x.b;
   }
   
   XMLColor& operator=(const XMLColor &x){
     this->r=x.r; this->g=x.g; this->b=x.b;
     return *this;
   }
   
   ~XMLColor(){}
   
   string str() const; 

   bool operator==(const XMLColor &col) const {
     return ((r==col.r)&&(g==col.g)&&(b==col.b));
   }

};  


class XMLFont {

private:
    double size;
    double line_size;
    bool italic;
    bool bold;
    string *font_name;
    string *font_family;
    XMLColor color;

public:  
    XMLFont(const char *font_family=DEFAULT_FONT_FAMILY, double size=12.0) : 
        size(size), line_size(-1.0), italic(false), bold(false),
        font_name(new string(font_family)), font_family(new string(font_family)),
        color() {}

    XMLFont(string* font_name, double size, GfxRGB rgb);    
    XMLFont(const XMLFont& other) :
        size(other.size), line_size(other.line_size), italic(other.italic),
        bold(other.bold), font_name(new string(*other.font_name)),
        font_family(other.font_family), color(other.color) {}

    XMLColor get_color() { return this->color; }
    string* get_font_name() { return this->font_name; }
    double get_size() const { return this->size; }
    double get_line_size() { return this->line_size; }
    void set_line_size(double ls) { this->line_size = ls; } 
    bool is_italic() const { return this->italic; }
    bool is_bold() const { return this->bold; }
    ~XMLFont() { delete this->font_name; delete this->font_family; }
    XMLFont& operator=(const XMLFont& other);
    bool operator==(const XMLFont &other) const;
    bool eq_upto_inline(const XMLFont &f) const;
    string str(vector<XMLFont*>::size_type id) const;
};

class Fonts : public vector<XMLFont*> {
    public:
        Fonts::size_type add_font(XMLFont *f);
        Fonts::size_type add_font(string* font_name, double size, GfxRGB rgb); 
        ~Fonts();
};


}
