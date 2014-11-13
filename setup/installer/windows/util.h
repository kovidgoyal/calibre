/*
 * Copyright 2009 Kovid Goyal
 */

#pragma once

#ifndef _UNICODE
#define _UNICODE
#endif

#ifndef UNICODE
#define UNICODE
#endif

#define _WIN32_WINNT 0x0502 

#include <windows.h>
#ifdef _DLL
#   include <Python.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <Shellapi.h>

#define DllExport __declspec( dllexport )
#define DllImport __declspec( dllimport )

#ifdef _DLL
#   define ExIm DllExport
#   pragma comment(lib, "delayimp")
#   pragma comment(lib, "user32")
#   pragma comment(lib, "shell32")
#else
#   define ExIm DllImport
#endif

ExIm void set_gui_app(char yes);
ExIm char is_gui_app();

// Redirect output streams to NUL
ExIm void redirect_out_stream(FILE *stream);

// Execute python entry point defined by: module and function
ExIm int execute_python_entrypoint(const char *basename, const char *module, const char *function);

