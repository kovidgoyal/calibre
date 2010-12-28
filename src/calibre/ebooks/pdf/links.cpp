/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */



#include "links.h"
#include "utils.h"

using namespace std;
using namespace calibre_reflow;

XMLLink& XMLLink::operator=(const XMLLink &x) {
    if (this==&x) return *this;
    if (this->dest) {delete this->dest; this->dest=NULL;} 
    this->x_min = x.x_min;
    this->y_min = x.y_min;
    this->x_max = x.x_max;
    this->y_max = x.y_max;
    this->dest = new string(*x.dest);
    return *this;
}

bool XMLLink::in_link(double xmin,double ymin,double xmax,double ymax) const {
    double y = (ymin + ymax)/2;
    if (y > this->y_max) return false;
    return (y > this->y_min) && (xmin < this->x_max) && (xmax > this->x_min);
}

string XMLLink::get_link_start() {
    ostringstream oss;
    oss << "<a href=\"";
    if (this->dest) oss << encode_for_xml(*this->dest);
    oss << "\">";
    return oss.str();
}

XMLLinks::~XMLLinks() {
    for(XMLLinks::iterator i = this->begin(); i != this->end(); i++)
        delete *i;
    this->clear();
}

bool XMLLinks::in_link(double xmin, double ymin, double xmax,
        double ymax, XMLLinks::size_type &p) const {
    for(XMLLinks::const_iterator i = this->begin(); i != this->end(); i++) {
        if ( (*i)->in_link(xmin, ymin, xmax, ymax) ) {
            p = (i - this->begin());
            return true;
        }
    }
    return false;
}


