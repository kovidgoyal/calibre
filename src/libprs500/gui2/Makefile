UI = main_ui.py dialogs/metadata_single_ui.py dialogs/metadata_bulk_ui.py dialogs/jobs_ui.py
RC = images_rc.pyc

%_ui.py : %.ui
	pyuic4 $< > $@

%_rc.pyc : %.qrc %
	pyrcc4 $< > $*_rc.py
	python -c "import compiler; compiler.compileFile('$*_rc.py')"

all : $(UI) $(RC)


clean :
	rm -f $(UI) $(RC)

test : all
	python main.py
