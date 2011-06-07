/*
 * Memory DLL loading code
 * Version 0.0.2 with additions from Thomas Heller
 *
 * Copyright (c) 2004-2005 by Joachim Bauch / mail@joachim-bauch.de
 * http://www.joachim-bauch.de
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is MemoryModule.c
 *
 * The Initial Developer of the Original Code is Joachim Bauch.
 *
 * Portions created by Joachim Bauch are Copyright (C) 2004-2005
 * Joachim Bauch. All Rights Reserved.
 *
 * Portions Copyright (C) 2005 Thomas Heller.
 *
 */

// disable warnings about pointer <-> DWORD conversions
#pragma warning( disable : 4311 4312 )

#include <Windows.h>
#include <winnt.h>
#if DEBUG_OUTPUT
#include <stdio.h>
#endif

#ifndef IMAGE_SIZEOF_BASE_RELOCATION
// Vista SDKs no longer define IMAGE_SIZEOF_BASE_RELOCATION!?
# define IMAGE_SIZEOF_BASE_RELOCATION (sizeof(IMAGE_BASE_RELOCATION))
#endif
#include "MemoryModule.h"

/*
  XXX We need to protect at least walking the 'loaded' linked list with a lock!
*/

/******************************************************************/
FINDPROC findproc;
void *findproc_data = NULL;

struct NAME_TABLE {
	char *name;
	DWORD ordinal;
};

typedef struct tagMEMORYMODULE {
	PIMAGE_NT_HEADERS headers;
	unsigned char *codeBase;
	HMODULE *modules;
	int numModules;
	int initialized;

	struct NAME_TABLE *name_table;

	char *name;
	int refcount;
	struct tagMEMORYMODULE *next, *prev;
} MEMORYMODULE, *PMEMORYMODULE;

typedef BOOL (WINAPI *DllEntryProc)(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved);

#define GET_HEADER_DICTIONARY(module, idx)	&(module)->headers->OptionalHeader.DataDirectory[idx]

MEMORYMODULE *loaded; /* linked list of loaded memory modules */

/* private - insert a loaded library in a linked list */
static void _Register(char *name, MEMORYMODULE *module)
{
	module->next = loaded;
	if (loaded)
		loaded->prev = module;
	module->prev = NULL;
	loaded = module;
}

/* private - remove a loaded library from a linked list */
static void _Unregister(MEMORYMODULE *module)
{
	free(module->name);
	if (module->prev)
		module->prev->next = module->next;
	if (module->next)
		module->next->prev = module->prev;
	if (module == loaded)
		loaded = module->next;
}

/* public - replacement for GetModuleHandle() */
HMODULE MyGetModuleHandle(LPCTSTR lpModuleName)
{
	MEMORYMODULE *p = loaded;
	while (p) {
		// If already loaded, only increment the reference count
		if (0 == stricmp(lpModuleName, p->name)) {
			return (HMODULE)p;
		}
		p = p->next;
	}
	return GetModuleHandle(lpModuleName);
}

/* public - replacement for LoadLibrary, but searches FIRST for memory
   libraries, then for normal libraries.  So, it will load libraries AS memory
   module if they are found by findproc().
*/
HMODULE MyLoadLibrary(char *lpFileName)
{
	MEMORYMODULE *p = loaded;
	HMODULE hMod;

	while (p) {
		// If already loaded, only increment the reference count
		if (0 == stricmp(lpFileName, p->name)) {
			p->refcount++;
			return (HMODULE)p;
		}
		p = p->next;
	}
	if (findproc && findproc_data) {
		void *pdata = findproc(lpFileName, findproc_data);
		if (pdata) {
			hMod = MemoryLoadLibrary(lpFileName, pdata);
			free(p);
			return hMod;
		}
	}
	hMod = LoadLibrary(lpFileName);
	return hMod;
}

/* public - replacement for GetProcAddress() */
FARPROC MyGetProcAddress(HMODULE hModule, LPCSTR lpProcName)
{
	MEMORYMODULE *p = loaded;
	while (p) {
		if ((HMODULE)p == hModule)
			return MemoryGetProcAddress(p, lpProcName);
		p = p->next;
	}
	return GetProcAddress(hModule, lpProcName);
}

/* public - replacement for FreeLibrary() */
BOOL MyFreeLibrary(HMODULE hModule)
{
	MEMORYMODULE *p = loaded;
	while (p) {
		if ((HMODULE)p == hModule) {
			if (--p->refcount == 0) {
				_Unregister(p);
				MemoryFreeLibrary(p);
			}
			return TRUE;
		}
		p = p->next;
	}
	return FreeLibrary(hModule);
}

#if DEBUG_OUTPUT
static void
OutputLastError(const char *msg)
{
	LPVOID tmp;
	char *tmpmsg;
	FormatMessage(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
		NULL, GetLastError(), MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPTSTR)&tmp, 0, NULL);
	tmpmsg = (char *)LocalAlloc(LPTR, strlen(msg) + strlen(tmp) + 3);
	sprintf(tmpmsg, "%s: %s", msg, tmp);
	OutputDebugString(tmpmsg);
	LocalFree(tmpmsg);
	LocalFree(tmp);
}
#endif

/*
static int dprintf(char *fmt, ...)
{
	char Buffer[4096];
	va_list marker;
	int result;
	
	va_start(marker, fmt);
	result = vsprintf(Buffer, fmt, marker);
	OutputDebugString(Buffer);
	return result;
}
*/

static void
CopySections(const unsigned char *data, PIMAGE_NT_HEADERS old_headers, PMEMORYMODULE module)
{
	int i, size;
	unsigned char *codeBase = module->codeBase;
	unsigned char *dest;
	PIMAGE_SECTION_HEADER section = IMAGE_FIRST_SECTION(module->headers);
	for (i=0; i<module->headers->FileHeader.NumberOfSections; i++, section++)
	{
		if (section->SizeOfRawData == 0)
		{
			// section doesn't contain data in the dll itself, but may define
			// uninitialized data
			size = old_headers->OptionalHeader.SectionAlignment;
			if (size > 0)
			{
				dest = (unsigned char *)VirtualAlloc(codeBase + section->VirtualAddress,
					size,
					MEM_COMMIT,
					PAGE_READWRITE);

				section->Misc.PhysicalAddress = (DWORD)dest;
				memset(dest, 0, size);
			}

			// section is empty
			continue;
		}

		// commit memory block and copy data from dll
		dest = (unsigned char *)VirtualAlloc(codeBase + section->VirtualAddress,
							section->SizeOfRawData,
							MEM_COMMIT,
							PAGE_READWRITE);
		memcpy(dest, data + section->PointerToRawData, section->SizeOfRawData);
		section->Misc.PhysicalAddress = (DWORD)dest;
	}
}

// Protection flags for memory pages (Executable, Readable, Writeable)
static int ProtectionFlags[2][2][2] = {
	{
		// not executable
		{PAGE_NOACCESS, PAGE_WRITECOPY},
		{PAGE_READONLY, PAGE_READWRITE},
	}, {
		// executable
		{PAGE_EXECUTE, PAGE_EXECUTE_WRITECOPY},
		{PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE},
	},
};

static void
FinalizeSections(PMEMORYMODULE module)
{
	int i;
	PIMAGE_SECTION_HEADER section = IMAGE_FIRST_SECTION(module->headers);
	
	// loop through all sections and change access flags
	for (i=0; i<module->headers->FileHeader.NumberOfSections; i++, section++)
	{
		DWORD protect, oldProtect, size;
		int executable = (section->Characteristics & IMAGE_SCN_MEM_EXECUTE) != 0;
		int readable =   (section->Characteristics & IMAGE_SCN_MEM_READ) != 0;
		int writeable =  (section->Characteristics & IMAGE_SCN_MEM_WRITE) != 0;

		if (section->Characteristics & IMAGE_SCN_MEM_DISCARDABLE)
		{
			// section is not needed any more and can safely be freed
			VirtualFree((LPVOID)section->Misc.PhysicalAddress, section->SizeOfRawData, MEM_DECOMMIT);
			continue;
		}

		// determine protection flags based on characteristics
		protect = ProtectionFlags[executable][readable][writeable];
		if (section->Characteristics & IMAGE_SCN_MEM_NOT_CACHED)
			protect |= PAGE_NOCACHE;

		// determine size of region
		size = section->SizeOfRawData;
		if (size == 0)
		{
			if (section->Characteristics & IMAGE_SCN_CNT_INITIALIZED_DATA)
				size = module->headers->OptionalHeader.SizeOfInitializedData;
			else if (section->Characteristics & IMAGE_SCN_CNT_UNINITIALIZED_DATA)
				size = module->headers->OptionalHeader.SizeOfUninitializedData;
		}

		if (size > 0)
		{
			// change memory access flags
			if (VirtualProtect((LPVOID)section->Misc.PhysicalAddress, section->SizeOfRawData, protect, &oldProtect) == 0)
#if DEBUG_OUTPUT
				OutputLastError("Error protecting memory page")
#endif
			;
		}
	}
}

static void
PerformBaseRelocation(PMEMORYMODULE module, DWORD delta)
{
	DWORD i;
	unsigned char *codeBase = module->codeBase;

	PIMAGE_DATA_DIRECTORY directory = GET_HEADER_DICTIONARY(module, IMAGE_DIRECTORY_ENTRY_BASERELOC);
	if (directory->Size > 0)
	{
		PIMAGE_BASE_RELOCATION relocation = (PIMAGE_BASE_RELOCATION)(codeBase + directory->VirtualAddress);
		for (; relocation->VirtualAddress > 0; )
		{
			unsigned char *dest = (unsigned char *)(codeBase + relocation->VirtualAddress);
			unsigned short *relInfo = (unsigned short *)((unsigned char *)relocation + IMAGE_SIZEOF_BASE_RELOCATION);
			for (i=0; i<((relocation->SizeOfBlock-IMAGE_SIZEOF_BASE_RELOCATION) / 2); i++, relInfo++)
			{
				DWORD *patchAddrHL;
				int type, offset;

				// the upper 4 bits define the type of relocation
				type = *relInfo >> 12;
				// the lower 12 bits define the offset
				offset = *relInfo & 0xfff;
				
				switch (type)
				{
				case IMAGE_REL_BASED_ABSOLUTE:
					// skip relocation
					break;

				case IMAGE_REL_BASED_HIGHLOW:
					// change complete 32 bit address
					patchAddrHL = (DWORD *)(dest + offset);
					*patchAddrHL += delta;
					break;

				default:
					//printf("Unknown relocation: %d\n", type);
					break;
				}
			}

			// advance to next relocation block
			relocation = (PIMAGE_BASE_RELOCATION)(((DWORD)relocation) + relocation->SizeOfBlock);
		}
	}
}

static int
BuildImportTable(PMEMORYMODULE module)
{
	int result=1;
	unsigned char *codeBase = module->codeBase;

	PIMAGE_DATA_DIRECTORY directory = GET_HEADER_DICTIONARY(module, IMAGE_DIRECTORY_ENTRY_IMPORT);
	if (directory->Size > 0)
	{
		PIMAGE_IMPORT_DESCRIPTOR importDesc = (PIMAGE_IMPORT_DESCRIPTOR)(codeBase + directory->VirtualAddress);
		for (; !IsBadReadPtr(importDesc, sizeof(IMAGE_IMPORT_DESCRIPTOR)) && importDesc->Name; importDesc++)
		{
			DWORD *thunkRef, *funcRef;
			HMODULE handle;

			handle = MyLoadLibrary(codeBase + importDesc->Name);
			if (handle == INVALID_HANDLE_VALUE)
			{
				//LastError should already be set
#if DEBUG_OUTPUT
				OutputLastError("Can't load library");
#endif
				result = 0;
				break;
			}

			module->modules = (HMODULE *)realloc(module->modules, (module->numModules+1)*(sizeof(HMODULE)));
			if (module->modules == NULL)
			{
				SetLastError(ERROR_NOT_ENOUGH_MEMORY);
				result = 0;
				break;
			}

			module->modules[module->numModules++] = handle;
			if (importDesc->OriginalFirstThunk)
			{
				thunkRef = (DWORD *)(codeBase + importDesc->OriginalFirstThunk);
				funcRef = (DWORD *)(codeBase + importDesc->FirstThunk);
			} else {
				// no hint table
				thunkRef = (DWORD *)(codeBase + importDesc->FirstThunk);
				funcRef = (DWORD *)(codeBase + importDesc->FirstThunk);
			}
			for (; *thunkRef; thunkRef++, funcRef++)
			{
				if IMAGE_SNAP_BY_ORDINAL(*thunkRef) {
					*funcRef = (DWORD)MyGetProcAddress(handle, (LPCSTR)IMAGE_ORDINAL(*thunkRef));
				} else {
					PIMAGE_IMPORT_BY_NAME thunkData = (PIMAGE_IMPORT_BY_NAME)(codeBase + *thunkRef);
					*funcRef = (DWORD)MyGetProcAddress(handle, (LPCSTR)&thunkData->Name);
				}
				if (*funcRef == 0)
				{
					SetLastError(ERROR_PROC_NOT_FOUND);
					result = 0;
					break;
				}
			}

			if (!result)
				break;
		}
	}

	return result;
}

/*
  MemoryLoadLibrary - load a library AS MEMORY MODULE, or return
  existing MEMORY MODULE with increased refcount.

  This allows to load a library AGAIN as memory module which is
  already loaded as HMODULE!

*/
HMEMORYMODULE MemoryLoadLibrary(char *name, const void *data)
{
	PMEMORYMODULE result;
	PIMAGE_DOS_HEADER dos_header;
	PIMAGE_NT_HEADERS old_header;
	unsigned char *code, *headers;
	DWORD locationDelta;
	DllEntryProc DllEntry;
	BOOL successfull;
	MEMORYMODULE *p = loaded;

	while (p) {
		// If already loaded, only increment the reference count
		if (0 == stricmp(name, p->name)) {
			p->refcount++;
			return (HMODULE)p;
		}
		p = p->next;
	}

	/* Do NOT check for GetModuleHandle here! */

	dos_header = (PIMAGE_DOS_HEADER)data;
	if (dos_header->e_magic != IMAGE_DOS_SIGNATURE)
	{
		SetLastError(ERROR_BAD_FORMAT);
#if DEBUG_OUTPUT
		OutputDebugString("Not a valid executable file.\n");
#endif
		return NULL;
	}

	old_header = (PIMAGE_NT_HEADERS)&((const unsigned char *)(data))[dos_header->e_lfanew];
	if (old_header->Signature != IMAGE_NT_SIGNATURE)
	{
		SetLastError(ERROR_BAD_FORMAT);
#if DEBUG_OUTPUT
		OutputDebugString("No PE header found.\n");
#endif
		return NULL;
	}

	// reserve memory for image of library
	code = (unsigned char *)VirtualAlloc((LPVOID)(old_header->OptionalHeader.ImageBase),
		old_header->OptionalHeader.SizeOfImage,
		MEM_RESERVE,
		PAGE_READWRITE);

    if (code == NULL)
        // try to allocate memory at arbitrary position
        code = (unsigned char *)VirtualAlloc(NULL,
            old_header->OptionalHeader.SizeOfImage,
            MEM_RESERVE,
            PAGE_READWRITE);
    
	if (code == NULL)
	{
		SetLastError(ERROR_NOT_ENOUGH_MEMORY);
#if DEBUG_OUTPUT
		OutputLastError("Can't reserve memory");
#endif
		return NULL;
	}

	result = (PMEMORYMODULE)HeapAlloc(GetProcessHeap(), 0, sizeof(MEMORYMODULE));
	result->codeBase = code;
	result->numModules = 0;
	result->modules = NULL;
	result->initialized = 0;
	result->next = result->prev = NULL;
	result->refcount = 1;
	result->name = strdup(name);
	result->name_table = NULL;

	// XXX: is it correct to commit the complete memory region at once?
    //      calling DllEntry raises an exception if we don't...
	VirtualAlloc(code,
		old_header->OptionalHeader.SizeOfImage,
		MEM_COMMIT,
		PAGE_READWRITE);

	// commit memory for headers
	headers = (unsigned char *)VirtualAlloc(code,
		old_header->OptionalHeader.SizeOfHeaders,
		MEM_COMMIT,
		PAGE_READWRITE);
	
	// copy PE header to code
	memcpy(headers, dos_header, dos_header->e_lfanew + old_header->OptionalHeader.SizeOfHeaders);
	result->headers = (PIMAGE_NT_HEADERS)&((const unsigned char *)(headers))[dos_header->e_lfanew];

	// update position
	result->headers->OptionalHeader.ImageBase = (DWORD)code;

	// copy sections from DLL file block to new memory location
	CopySections(data, old_header, result);

	// adjust base address of imported data
	locationDelta = (DWORD)(code - old_header->OptionalHeader.ImageBase);
	if (locationDelta != 0)
		PerformBaseRelocation(result, locationDelta);

	// load required dlls and adjust function table of imports
	if (!BuildImportTable(result))
		goto error;

	// mark memory pages depending on section headers and release
	// sections that are marked as "discardable"
	FinalizeSections(result);

	// get entry point of loaded library
	if (result->headers->OptionalHeader.AddressOfEntryPoint != 0)
	{
		DllEntry = (DllEntryProc)(code + result->headers->OptionalHeader.AddressOfEntryPoint);
		if (DllEntry == 0)
		{
			SetLastError(ERROR_BAD_FORMAT); /* XXX ? */
#if DEBUG_OUTPUT
			OutputDebugString("Library has no entry point.\n");
#endif
			goto error;
		}

		// notify library about attaching to process
		successfull = (*DllEntry)((HINSTANCE)code, DLL_PROCESS_ATTACH, 0);
		if (!successfull)
		{
#if DEBUG_OUTPUT
			OutputDebugString("Can't attach library.\n");
#endif
			goto error;
		}
		result->initialized = 1;
	}

	_Register(name, result);

	return (HMEMORYMODULE)result;

error:
	// cleanup
	free(result->name);
	MemoryFreeLibrary(result);
	return NULL;
}

int _compare(const struct NAME_TABLE *p1, const struct NAME_TABLE *p2)
{
	return stricmp(p1->name, p2->name);
}

int _find(const char **name, const struct NAME_TABLE *p)
{
	return stricmp(*name, p->name);
}

struct NAME_TABLE *GetNameTable(PMEMORYMODULE module)
{
	unsigned char *codeBase;
	PIMAGE_EXPORT_DIRECTORY exports;
	PIMAGE_DATA_DIRECTORY directory;
	DWORD i, *nameRef;
	WORD *ordinal;
	struct NAME_TABLE *p, *ptab;

	if (module->name_table)
		return module->name_table;

	codeBase = module->codeBase;
	directory = GET_HEADER_DICTIONARY(module, IMAGE_DIRECTORY_ENTRY_EXPORT);
	exports = (PIMAGE_EXPORT_DIRECTORY)(codeBase + directory->VirtualAddress);

	nameRef = (DWORD *)(codeBase + exports->AddressOfNames);
	ordinal = (WORD *)(codeBase + exports->AddressOfNameOrdinals);

	p = ((PMEMORYMODULE)module)->name_table = (struct NAME_TABLE *)malloc(sizeof(struct NAME_TABLE)
									      * exports->NumberOfNames);
	if (p == NULL)
		return NULL;
	ptab = p;
	for (i=0; i<exports->NumberOfNames; ++i) {
		p->name = (char *)(codeBase + *nameRef++);
		p->ordinal = *ordinal++;
		++p;
	}
	qsort(ptab, exports->NumberOfNames, sizeof(struct NAME_TABLE), _compare);
	return ptab;
}

FARPROC MemoryGetProcAddress(HMEMORYMODULE module, const char *name)
{
	unsigned char *codeBase = ((PMEMORYMODULE)module)->codeBase;
	int idx=-1;
	PIMAGE_EXPORT_DIRECTORY exports;
	PIMAGE_DATA_DIRECTORY directory = GET_HEADER_DICTIONARY((PMEMORYMODULE)module, IMAGE_DIRECTORY_ENTRY_EXPORT);

	if (directory->Size == 0)
		// no export table found
		return NULL;

	exports = (PIMAGE_EXPORT_DIRECTORY)(codeBase + directory->VirtualAddress);
	if (exports->NumberOfNames == 0 || exports->NumberOfFunctions == 0)
		// DLL doesn't export anything
		return NULL;

	if (HIWORD(name)) {
		struct NAME_TABLE *ptab;
		struct NAME_TABLE *found;
		ptab = GetNameTable((PMEMORYMODULE)module);
		if (ptab == NULL)
			// some failure
			return NULL;
		found = bsearch(&name, ptab, exports->NumberOfNames, sizeof(struct NAME_TABLE), _find);
		if (found == NULL)
			// exported symbol not found
			return NULL;
	
		idx = found->ordinal;
	}
	else
		idx = LOWORD(name) - exports->Base;

	if ((DWORD)idx > exports->NumberOfFunctions)
		// name <-> ordinal number don't match
		return NULL;
	
	// AddressOfFunctions contains the RVAs to the "real" functions
	return (FARPROC)(codeBase + *(DWORD *)(codeBase + exports->AddressOfFunctions + (idx*4)));
}

void MemoryFreeLibrary(HMEMORYMODULE mod)
{
	int i;
	PMEMORYMODULE module = (PMEMORYMODULE)mod;

	if (module != NULL)
	{
		if (module->initialized != 0)
		{
			// notify library about detaching from process
			DllEntryProc DllEntry = (DllEntryProc)(module->codeBase + module->headers->OptionalHeader.AddressOfEntryPoint);
			(*DllEntry)((HINSTANCE)module->codeBase, DLL_PROCESS_DETACH, 0);
			module->initialized = 0;
		}

		if (module->modules != NULL)
		{
			// free previously opened libraries
			for (i=0; i<module->numModules; i++)
				if (module->modules[i] != INVALID_HANDLE_VALUE)
					MyFreeLibrary(module->modules[i]);

			free(module->modules);
		}

		if (module->codeBase != NULL)
			// release memory of library
			VirtualFree(module->codeBase, 0, MEM_RELEASE);

		if (module->name_table != NULL)
			free(module->name_table);

		HeapFree(GetProcessHeap(), 0, module);
	}
}
