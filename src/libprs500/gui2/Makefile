UI = main_ui.py dialogs/metadata_single_ui.py dialogs/metadata_bulk_ui.py dialogs/jobs_ui.py \
     dialogs/conversion_error_ui.py dialogs/lrf_single_ui.py dialogs/choose_format_ui.py     \
     dialogs/password_ui.py lrf_renderer/main_ui.py lrf_renderer/config_ui.py
RC = images_rc.pyc

%_ui.py : %.ui
	pyuic4 $< | sed "s/import images_rc/from libprs500.gui2 import images_rc/" | \
		    sed "s/from library import/from libprs500.gui2.library import/"> $@

%_rc.pyc : %.qrc %
	pyrcc4 $< > $*_rc.py
	python -c "import compiler; compiler.compileFile('$*_rc.py')"

all : $(UI) $(RC)


clean :
	rm -f $(UI) $(RC)

test : all
	python main.py

lrfviewer: all
	python lrf_renderer/main.py
