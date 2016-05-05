/*
 * imageops.h
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#include <QImage>
#include <Python.h>

QImage* remove_borders(const QImage &image, double fuzz);

