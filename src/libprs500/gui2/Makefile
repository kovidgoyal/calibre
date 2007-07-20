all : main_ui.py images_rc.pyc

main_ui.py : main.ui
	pyuic4 main.ui > main_ui.py

images_rc.pyc : images.qrc images
	pyrcc4 images.qrc > images_rc.py
	python -c "import compiler; compiler.compileFile('images_rc.py')"
	echo > images_rc.py
	touch images_rc.pyc

clean :
	rm main_ui.py images_rc.pyc

test : all
	python main.py
