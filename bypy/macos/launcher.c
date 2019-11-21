#include "util.h"
#include <stdlib.h>
#include <libproc.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>

#define fatal(...) { fprintf(stderr, __VA_ARGS__); exit(EXIT_FAILURE); }
#define arraysz(x) (sizeof(x)/sizeof(x[0]))


int
main(int argc, char * const *argv) {
    run(PROGRAM, MODULE, FUNCTION, IS_GUI, argc, argv);
	return 0;
}
