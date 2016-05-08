/*
 * quantize.cpp
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * octree based image quantization. 
 * Based on https://www.microsoft.com/msj/archive/S3F1.aspx
 *
 * Distributed under terms of the GPL3 license.
 */

#include <algorithm>
#include <cmath>
#include <stdio.h>
#include <QVector>
#include "imageops.h"

#ifdef _MSC_VER
typedef unsigned __int64 uint64_t;
typedef __int64 int64_t;
typedef unsigned __int32 uint32_t;
#ifndef log2
static inline double log2(double x) { return log(x) / log((double)2) ; }
#endif
#else
#include <stdint.h>
#endif
#define MAX_DEPTH 8
#define MAX_COLORS 256
#define MAX(x, y) ((x) > (y)) ? (x) : (y)
#define MIN(x, y) ((x) < (y)) ? (x) : (y)
static const unsigned char BIT_MASK[8] = { 1 << 7, 1 << 6, 1 << 5, 1 << 4, 1 << 3, 1 << 2, 1 << 1, 1 };
static inline size_t get_index(const u_int32_t r, const uint32_t g, const u_int32_t b, const size_t level) {
    return ((((r & BIT_MASK[level]) >> (7 - level)) << 2) | (((g & BIT_MASK[level]) >> (7 - level)) << 1) | ((b & BIT_MASK[level]) >> (7 - level)));
}

class Node {
private:
    bool is_leaf;
    unsigned char index;
    uint64_t pixel_count;
    uint64_t red_sum;
    uint64_t green_sum;
    uint64_t blue_sum;
    Node* next_reducible_node;
    Node* children[MAX_DEPTH];

public:
#ifdef _MSC_VER
// Disable the new behavior warning caused by children() below
#pragma warning( push )
#pragma warning (disable: 4351)
    Node() : is_leaf(false), index(0), pixel_count(0), red_sum(0), green_sum(0), blue_sum(0), next_reducible_node(NULL), children() {}
#pragma warning ( pop )
#endif

    ~Node() {
        for (size_t i = 0; i < MAX_DEPTH; i++) { delete this->children[i]; this->children[i] = NULL; }
    }

    void check_compiler() {
        if (this->children[0] != NULL) throw std::runtime_error("Compiler failed to default initialize children");
    }

    inline Node* create_child(const size_t level, const size_t depth, unsigned int *leaf_count, Node **reducible_nodes) {
        Node *c = new Node();
        if (level == depth) { 
            c->is_leaf = true;
            (*leaf_count)++;
        } else {
            c->next_reducible_node = reducible_nodes[level];
            reducible_nodes[level] = c;
        }
        return c;
    }

    void add_color(const uint32_t r, const uint32_t g, const uint32_t b, const size_t depth, const size_t level, unsigned int *leaf_count, Node **reducible_nodes) {
        if (this->is_leaf) {
            this->pixel_count++;
            this->red_sum += r;
            this->green_sum += g;
            this->blue_sum += b;
        } else {
            size_t index = get_index(r, g, b, level);
            if (this->children[index] == NULL) this->children[index] = this->create_child(level, depth, leaf_count, reducible_nodes);
            this->children[index]->add_color(r, g, b, depth, level + 1, leaf_count, reducible_nodes);
        }
    }

    void reduce(const size_t depth, unsigned int *leaf_count, Node **reducible_nodes) {
        size_t i = 0;
        Node *node = NULL;

        // Find the deepest level containing at least one reducible node
        for (i=depth - 1; i > 0 && reducible_nodes[i] == NULL; i--);

        // Reduce the node most recently added to the list at level i
        // Could make this smarter by walking the linked list and choosing a
        // node that has the least number of pixels or by storing error info
        // on the nodes and using that
        node = reducible_nodes[i];
        reducible_nodes[i] = node->next_reducible_node;

        for (i = 0; i < MAX_DEPTH; i++) {
            if (node->children[i] != NULL) {
                node->red_sum += node->children[i]->red_sum;
                node->green_sum += node->children[i]->green_sum;
                node->blue_sum += node->children[i]->blue_sum;
                node->pixel_count += node->children[i]->pixel_count;
                delete node->children[i]; node->children[i] = NULL;
                (*leaf_count)--;
            }
        }
        node->is_leaf = true; *leaf_count += 1;
    }

    void set_palette_colors(QRgb *color_table, unsigned char *index) {
        int i;
        if (this->is_leaf) {
#define AVG_COLOR(x) ((int) ((double)this->x / (double)this->pixel_count))
            color_table[*index] = qRgb(AVG_COLOR(red_sum), AVG_COLOR(green_sum), AVG_COLOR(blue_sum)); 
            this->index = (*index)++;
        } else {
            for (i = 0; i < MAX_DEPTH; i++) {
                if (this->children[i] != NULL) this->children[i]->set_palette_colors(color_table, index);
            }
        }
    }

    unsigned char index_for_color(const uint32_t r, const uint32_t g, const uint32_t b, const size_t level) const {
        if (this->is_leaf) return this->index;
        size_t index = get_index(r, g, b, level);
        if (this->children[index] == NULL) throw std::out_of_range("Something bad happened: could not follow tree for color");
        return this->children[index]->index_for_color(r, g, b, level + 1);
    }
};

QImage quantize(const QImage &image, unsigned int maximum_colors, bool dither) {
    size_t depth = 0;
    int iwidth = image.width(), iheight = image.height(), r, c;
    QImage img(image), ans(iwidth, iheight, QImage::Format_Indexed8);
    unsigned int leaf_count = 0;
    unsigned char index = 0;
    Node* reducible_nodes[MAX_DEPTH + 1] = {0};
    Node root = Node();
    QVector<QRgb> color_table = QVector<QRgb>(MAX_COLORS);
    const QRgb* line = NULL;
    unsigned char *bits = NULL;

    root.check_compiler();

    maximum_colors = MAX(2, MIN(MAX_COLORS, maximum_colors));
    if (img.colorCount() > 0 && (size_t)img.colorCount() <= maximum_colors) return img; // Image is already quantized
    if (img.hasAlphaChannel()) throw std::out_of_range("Cannot quantize image with transparency");
    // TODO: Handle indexed image with colors > maximum_colors more efficiently
    // by iterating over the color table rather than the pixels
    if (img.format() != QImage::Format_RGB32) img = img.convertToFormat(QImage::Format_RGB32);
    if (img.isNull()) throw std::bad_alloc();

    depth = (size_t)log2(maximum_colors);
    depth = MAX(2, MIN(depth, MAX_DEPTH));

    for (r = 0; r < iheight; r++) {
        line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        for (c = 0; c < iwidth; c++) {
            const QRgb pixel = *(line + c);
            root.add_color(qRed(pixel), qGreen(pixel), qBlue(pixel), depth, 0, &leaf_count, reducible_nodes);
            while (leaf_count > maximum_colors)
                root.reduce(depth, &leaf_count, reducible_nodes);
        }
    }

    if (leaf_count > maximum_colors) throw std::out_of_range("Leaf count > max colors, something bad happened");
    color_table.resize(leaf_count);
    root.set_palette_colors(color_table.data(), &index);
    ans.setColorTable(color_table);

    for (r = 0; r < iheight; r++) {
        line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        bits = ans.scanLine(r);
        for (c = 0; c < iwidth; c++) {
            const QRgb pixel = *(line + c);
            *(bits + c) = root.index_for_color(qRed(pixel), qGreen(pixel), qBlue(pixel), 0);
        }
    }

    return ans;
}
