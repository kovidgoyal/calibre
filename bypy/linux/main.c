#include "util.h"

#include <stdlib.h>

int
main(int argc, char **argv) {
	execute_python_entrypoint(argc, argv, BASENAME, MODULE, FUNCTION, GUI_APP);
    return 0;
}
