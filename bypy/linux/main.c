#include "util.h"

#include <stdlib.h>

int main(int argc, char **argv) {
    int ret = 0;
    set_gui_app(GUI_APP);
	ret = execute_python_entrypoint(argc, argv, BASENAME, MODULE, FUNCTION);

    return ret;
}
