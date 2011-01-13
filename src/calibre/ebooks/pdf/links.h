/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */



#pragma once
#include <vector>
#include <sstream>

using namespace std;

namespace calibre_reflow {

class XMLLink {

private:  
  double x_min;
  double y_min;
  double x_max;
  double y_max;
  string* dest;

public:
  XMLLink() : dest(NULL) {}
  XMLLink(const XMLLink& x) : 
      x_min(x.x_min), y_min(x.y_min), x_max(x.x_max),
      y_max(x.y_max), dest(new string(*x.dest)) {}
  XMLLink(double x_min, double y_min, double x_max,
          double y_max, const char *dest) :
      x_min((x_min < x_max) ? x_min : x_max),
      y_min((y_min < y_max) ? y_min : y_max),
      x_max((x_max > x_min) ? x_max : x_min),
      y_max((y_max > y_min) ? y_max : y_min),
      dest(new string(dest)) {}

  ~XMLLink() { delete this->dest; }

  string* get_dest() { return this->dest; }
  double  get_x1() const {return x_min;}
  double  get_x2() const {return x_max;}
  double  get_y1() const {return y_min;}
  double  get_y2() const {return y_max;}

  XMLLink& operator=(const XMLLink &x);
  bool operator==(const XMLLink &x) const {
      return (this->dest != NULL) && (x.dest != NULL) && 
          this->dest->compare(*x.dest) == 0;
  }
  bool in_link(double xmin, double ymin, double xmax, double ymax) const;
  string get_link_start();
  
};

class XMLLinks : public vector<XMLLink*> {
    public:
        ~XMLLinks();

        bool in_link(double xmin, double ymin, double xmax,
                    double ymax, XMLLinks::size_type &p) const;
};


}
   
