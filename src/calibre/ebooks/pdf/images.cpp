/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */



#include <stdio.h>
#include <errno.h>
#include <sstream>
#include <algorithm>
#include <iomanip>
#include <math.h>
#include <iostream>
#include <wand/MagickWand.h>

#include "images.h"
#include "utils.h"

#ifdef _WIN32
inline double round(double x) { return (x-floor(x))>0.5 ? ceil(x) : floor(x); }
#endif

#define xoutRound(x) ( static_cast<int>(round(x)) )
using namespace std;
using namespace calibre_reflow;

calibre_reflow::ImageInfo::ImageInfo(GfxState *state) {
    // get image position and size
    state->transform(0, 0, &xt, &yt);
    state->transformDelta(1, 1, &wt, &ht);
    if (wt > 0) {
        x0 = xoutRound(xt);
        w0 = xoutRound(wt);
    } else {
        x0 = xoutRound(xt + wt);
        w0 = xoutRound(-wt);
    }
    if (ht > 0) {
        y0 = xoutRound(yt);
        h0 = xoutRound(ht);
    } else {
        y0 = xoutRound(yt + ht);
        h0 = xoutRound(-ht);
    }
    state->transformDelta(1, 0, &xt, &yt);
    rotate = fabs(xt) < fabs(yt);
    if (rotate) {
        w1 = h0;
        h1 = w0;
        x_flip = ht < 0;
        y_flip = wt > 0;
    } else {
        w1 = w0;
        h1 = h0;
        x_flip = wt < 0;
        y_flip = ht > 0;
    }
    //cout << x_flip << "|" << y_flip << endl;
}

void XMLImages::clear() {
    vector<XMLImage*>::iterator it;
    for (it = this->masks.begin(); it < this->masks.end(); it++)
        delete *it;
    for (it = this->images.begin(); it < this->images.end(); it++)
        delete *it;
    this->masks.clear();
    this->images.clear();
}

void XMLImages::add_mask(GfxState *state, Object *ref, Stream *str,
				  unsigned int width, unsigned int height, bool invert,
				  bool interpolate, bool inline_img) {
}

static void throw_magick_exception(MagickWand *wand) {
    ExceptionType severity;
    char *description = MagickGetException(wand, &severity);
    ostringstream oss;
    oss << description << endl;
    description=(char *) MagickRelinquishMemory(description);
    wand = DestroyMagickWand(wand);
    MagickWandTerminus();
    throw ReflowException(oss.str().c_str());
}


static void flip_image(string file_name, bool x_flip, bool y_flip) {
    MagickWand *magick_wand;
    MagickBooleanType status;

    MagickWandGenesis();
    magick_wand = NewMagickWand();
    status = MagickReadImage(magick_wand, file_name.c_str());
    if (status == MagickFalse) throw_magick_exception(magick_wand);

    if (y_flip) {
        status = MagickFlipImage(magick_wand);
        if (status == MagickFalse) throw_magick_exception(magick_wand);
    }
    if (x_flip) {
        status = MagickFlopImage(magick_wand);
        if (status == MagickFalse) throw_magick_exception(magick_wand);
    }

    status = MagickWriteImage(magick_wand, NULL);
    if (status == MagickFalse) throw_magick_exception(magick_wand);

    magick_wand = DestroyMagickWand(magick_wand);
    MagickWandTerminus();
}

void XMLImages::add(GfxState *state, Object *ref, Stream *str,
			      unsigned int width, unsigned int height, GfxImageColorMap *colorMap,
			      bool interpolate, int *maskColors, bool inline_img) {
    XMLImage *img = new XMLImage(state);
    this->images.push_back(img); 
    img->width = width; img->height = height;
    img->type = (str->getKind() == strDCT) ? jpeg : png;
    string file_name = this->file_name(img);

    FILE *of = fopen(file_name.c_str(), "wb");
    if (!of) throw ReflowException(strerror(errno));

    if (img->type == jpeg) {
        int c;
        str = ((DCTStream *)str)->getRawStream();
        str->reset();

        // copy the stream
        while ((c = str->getChar()) != EOF) fputc(c, of);
    } else { //Render as PNG
        Guchar *p;
        GfxRGB rgb;
        png_byte *row = (png_byte *) malloc(3 * width);   // 3 bytes/pixel: RGB
        png_bytep *row_pointer= &row;

        PNGWriter *writer = new PNGWriter();
        writer->init(of, width, height); 

        // Initialize the image stream
        ImageStream *imgStr = new ImageStream(str, width,
                            colorMap->getNumPixelComps(), colorMap->getBits());
        imgStr->reset();

        // For each line...
        for (unsigned int y = 0; y < height; y++) {
            // Convert into a PNG row
            p = imgStr->getLine();
            for (unsigned int x = 0; x < width; x++) {
                colorMap->getRGB(p, &rgb);
                // Write the RGB pixels into the row
                row[3*x]= colToByte(rgb.r);
                row[3*x+1]= colToByte(rgb.g);
                row[3*x+2]= colToByte(rgb.b);
                p += colorMap->getNumPixelComps();
            }

            writer->writeRow(row_pointer);
        }

        writer->close();
        delete writer;

        free(row);
        imgStr->close();
        delete imgStr;

    }
    fclose(of);
    img->written = true;
    if (img->info.x_flip || img->info.y_flip)
        flip_image(file_name, img->info.x_flip, img->info.y_flip);
}


string XMLImages::file_name(const XMLImage *img) const {
    vector<XMLImage*>::const_iterator ir, mr;
    size_t idx = 0;
    bool mask = false;

    ir = find( this->images.begin(), this->images.end(), img);
    if (ir == this->images.end()) {
        mr = find( this->masks.begin(), this->masks.end(), img);
        idx = mr - this->masks.begin();
        mask = true;
    } else idx = ir - this->images.begin();

    ostringstream oss;
    oss << ((mask) ? "mask" : "image") << "-" << idx+1 << '.';
    oss << ((img->type == jpeg) ? "jpg" : "png");
    return oss.str();
}

vector<string*> XMLImages::str() const {
    vector<string*> ans;
    vector <XMLImage*>::const_iterator it;
    for (it = this->masks.begin(); it < this->masks.end(); it++) {
        if ((*it)->written) 
           ans.push_back(new string((*it)->str(it - this->masks.begin(), true,
                           this->file_name(*it)))); 
    }
    for (it = this->images.begin(); it < this->images.end(); it++) {
        if ((*it)->written) 
           ans.push_back(new string((*it)->str(it - this->images.begin(), false,
                           this->file_name(*it)))); 
    }
    return ans; 
}

string XMLImage::str(size_t num, bool mask, string file_name) const {
    ostringstream oss;
    oss << "<img type=\"" << ((mask) ? "mask" : "image") << "\" "
        << "src=\"" << file_name << "\" "
        << "iwidth=\"" << this->width << "\" iheight=\"" << this->height << "\" "
        << "rwidth=\"" << this->info.w1 << "\" rheight=\"" << this->info.h1 << "\" "
        << setiosflags(ios::fixed) << setprecision(2)
        << "top=\"" << this->info.y0 << "\" left=\"" << this->info.x0 << "\"/>";
    return oss.str();


}
PNGWriter::~PNGWriter()
{
	/* cleanup heap allocation */
	png_destroy_write_struct(&png_ptr, &info_ptr);
}

void PNGWriter::init(FILE *f, int width, int height)
{
	/* initialize stuff */
	png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
	if (!png_ptr) 
        throw ReflowException("png_create_write_struct failed");

	info_ptr = png_create_info_struct(png_ptr);
	if (!info_ptr) 
		throw ReflowException("png_create_info_struct failed");

	if (setjmp(png_jmpbuf(png_ptr))) 
		throw ReflowException("png_jmpbuf failed");

	/* write header */
	png_init_io(png_ptr, f);
	if (setjmp(png_jmpbuf(png_ptr))) 
		throw ReflowException("Error during writing header");
	
	// Set up the type of PNG image and the compression level
	png_set_compression_level(png_ptr, Z_BEST_COMPRESSION);

	png_byte bit_depth = 8;
	png_byte color_type = PNG_COLOR_TYPE_RGB;
	png_byte interlace_type = PNG_INTERLACE_NONE;

	png_set_IHDR(png_ptr, info_ptr, width, height, bit_depth, color_type, interlace_type, PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);

	png_write_info(png_ptr, info_ptr);
	if (setjmp(png_jmpbuf(png_ptr))) 
		throw ReflowException("error during writing png info bytes");
	
}

void PNGWriter::writePointers(png_bytep *rowPointers)
{
	png_write_image(png_ptr, rowPointers);
	/* write bytes */
	if (setjmp(png_jmpbuf(png_ptr))) 
        throw ReflowException("Error during writing bytes");
}

void PNGWriter::writeRow(png_bytep *row)
{
	// Write the row to the file
	png_write_rows(png_ptr, row, 1);
	if (setjmp(png_jmpbuf(png_ptr))) 
		throw ReflowException("error during png row write");
}

void PNGWriter::close()
{
	/* end write */
	png_write_end(png_ptr, info_ptr);
	if (setjmp(png_jmpbuf(png_ptr))) 
		throw ReflowException("Error during end of write");
}

void PNGWriter::write_splash_bitmap(SplashBitmap *bitmap) {
    SplashColorPtr row = bitmap->getDataPtr();
    int height = bitmap->getHeight();
    int row_size = bitmap->getRowSize();
    png_bytep *row_pointers = new png_bytep[height];

    for (int y = 0; y < height; ++y) {
        row_pointers[y] = row;
        row += row_size;
    }
    this->writePointers(row_pointers);
    delete[] row_pointers;
}

void calibre_png_mem_write(png_structp png_ptr, png_bytep data, png_size_t length) {
    if (!png_ptr || length < 1) return;
    vector<char> *buf = static_cast< vector<char>* >(png_ptr->io_ptr);
    buf->reserve(buf->capacity() + length); 
    do {
        buf->push_back(static_cast<char>(*data));
        data++; length--;
    } while(length > 0);
}

void calibre_png_mem_flush(png_structp png_ptr) {}

void PNGMemWriter::init(vector<char> *buf, int width, int height) {
    /* initialize stuff */
    this->png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    if (!this->png_ptr) 
        throw ReflowException("png_create_write_struct failed");

    this->info_ptr = png_create_info_struct(png_ptr);
    if (!this->info_ptr) 
        throw ReflowException("png_create_info_struct failed");

    if (setjmp(png_jmpbuf(this->png_ptr))) 
        throw ReflowException("png_jmpbuf failed");

    png_set_write_fn(this->png_ptr, static_cast<void *>(buf),
            calibre_png_mem_write, calibre_png_mem_flush);
    if (setjmp(png_jmpbuf(this->png_ptr))) 
        throw ReflowException("png_set_write failed");


    // Set up the type of PNG image and the compression level
    png_set_compression_level(this->png_ptr, Z_BEST_COMPRESSION);

    png_byte bit_depth = 8;
    png_byte color_type = PNG_COLOR_TYPE_RGB;
    png_byte interlace_type = PNG_INTERLACE_NONE;

    png_set_IHDR(this->png_ptr, this->info_ptr, width, height,
            bit_depth, color_type, interlace_type,
            PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);

    png_write_info(png_ptr, info_ptr);
    if (setjmp(png_jmpbuf(png_ptr))) 
        throw ReflowException("error during writing png info bytes");

}

/*
void calibre_jpeg_error_exit (j_common_ptr cinfo)
{
    // cinfo->err really points to a my_error_mgr struct, so coerce pointer 
    calibre_jpeg_err_mgr *err = (calibre_jpeg_err_mgr *)(cinfo->err);

    // Always display the message. 
    // We could postpone this until after returning, if we chose. 
    //(*cinfo->err->output_message) (cinfo);

    // Return control to the setjmp point 
    longjmp(err->setjmp_buffer, 1);
}


JPEGWriter::JPEGWriter() {
    this->cinfo.err = jpeg_std_error(&this->jerr.pub);
    jpeg_create_compress(&this->cinfo);
    this->jerr.pub.error_exit = calibre_jpeg_error_exit;
    this->check();
    this->outfile = NULL;
}

void JPEGWriter::init(int width, int height) {
    cinfo.image_width = width; 
    cinfo.image_height = height;
    cinfo.input_components = 3;       // # of color components per pixel 
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&this->cinfo);
    this->check();
    jpeg_start_compress(&this->cinfo, TRUE);
    this->check();
}

void JPEGWriter::init_io(FILE *f) {
    jpeg_stdio_dest(&this->cinfo, f);
    this->check();
    this->outfile = f;
}

void JPEGWriter::check() {
    if (setjmp(jerr.setjmp_buffer)) this->raise();
}

void JPEGWriter::raise() {
    char buffer[JMSG_LENGTH_MAX];

    // Create the message 
    (*this->cinfo.err->format_message) ((jpeg_common_struct *)(&this->cinfo), buffer);
    jpeg_destroy_compress(&this->cinfo);
    throw ReflowException(buffer);
}

void JPEGWriter::write_image(JSAMPARRAY image_buffer, JDIMENSION num) {
    size_t num_written = jpeg_write_scanlines(&this->cinfo, image_buffer, num);
    this->check();
    if (num_written != num) {
        jpeg_destroy_compress(&this->cinfo);
        throw ReflowException("Failed to write all JPEG scanlines.");
    }
}

void JPEGWriter::write_splash_bitmap(SplashBitmap *bitmap) {
    SplashColorPtr row = bitmap->getDataPtr();
    int height = bitmap->getHeight();
    int row_size = bitmap->getRowSize();
    JSAMPARRAY row_pointers = new JSAMPLE*[height];

    for (int y = 0; y < height; ++y) {
        row_pointers[y] = row;
        row += row_size;
    }
    this->write_image(row_pointers, height);
    delete[] row_pointers;
    jpeg_finish_compress(&this->cinfo);
    this->check();
    fclose(this->outfile);
}

JPEGWriter::~JPEGWriter() {
    jpeg_destroy_compress(&this->cinfo);
}
*/
