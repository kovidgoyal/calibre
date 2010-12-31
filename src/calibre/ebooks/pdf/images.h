/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */



#pragma once

#include <vector>
#include <GfxState.h>
#include <splash/SplashBitmap.h>
#include <png.h>
#include <jpeglib.h>
#include "utils.h"

using namespace std;

namespace calibre_reflow {

    enum ImageType {
        jpeg, png
    };

    class PNGWriter
    {
        public:
            PNGWriter() {}
            ~PNGWriter();

            void init(FILE *f, int width, int height);

            void writePointers(png_bytep *rowPointers);
            void writeRow(png_bytep *row);
            void write_splash_bitmap(SplashBitmap *bitmap);
            void close();

        protected:
            png_structp png_ptr;
            png_infop info_ptr;
    };


    class PNGMemWriter : public PNGWriter
    {

        public:
            void init(vector<char> *buf, int width, int height);
    };

    class ImageInfo {
        public:

            ImageInfo(GfxState *state);

        private:
            int x0, y0;			// top left corner of image
            int w0, h0, w1, h1;		// size of image
            double xt, yt, wt, ht;
            bool rotate, x_flip, y_flip;

            friend class XMLImage; 
            friend class XMLImages;

    };

    class XMLImage {
        private:
            double x, y;
            unsigned int width, height;
            ImageType type;
            bool written;
            ImageInfo info;

            friend class XMLImages;

        public:
            XMLImage(GfxState *state) :
                x(0.), y(0.), width(0), height(0), type(jpeg), written(false), info(state)
            {}

            ~XMLImage() {}

            string str(size_t num, bool mask, string file_name) const;
    };

    class XMLImages {
        private:
            vector<XMLImage*> images;
            vector<XMLImage*> masks;

        public:

            ~XMLImages() { this->clear(); }

            void add_mask(GfxState *state, Object *ref, Stream *str,
				  unsigned int width, unsigned int height, bool invert,
				  bool interpolate, bool inline_img);

            void add(GfxState *state, Object *ref, Stream *str,
			      unsigned int width, unsigned int height, GfxImageColorMap *colorMap,
			      bool interpolate, int *maskColors, bool inline_img);

            string file_name(const XMLImage *img) const;
            vector<string*> str() const;
            void clear();
    };
/*
    struct calibre_jpeg_err_mgr {
        struct jpeg_error_mgr pub;    // "public" fields 

        jmp_buf setjmp_buffer;    // for return to caller 
    };

    class JPEGWriter {
        private:
            FILE *outfile;
            
        protected:
            struct jpeg_compress_struct cinfo;
            struct calibre_jpeg_err_mgr jerr;

            void raise();
            void check();

        public:
            JPEGWriter();
            ~JPEGWriter();
            void init_io(FILE *f);
            void init(int width, int height);
            void write_image(JSAMPARRAY image_buffer, JDIMENSION number_of_scanlines);
            void write_splash_bitmap(SplashBitmap *bitmap);
    };
*/
}
