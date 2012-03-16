# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS   =
SPHINXBUILD  = sphinx-build
PAPER        =

ALLSPHINXOPTS = -d .build/doctrees -D latex_paper_size=$(PAPER) \
                $(SPHINXOPTS) .

.PHONY: help clean html web htmlhelp latex changes linkcheck

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  html      to make standalone HTML files"
	@echo "  web       to make files usable by Sphinx.web"
	@echo "  htmlhelp  to make HTML files and a HTML help project"
	@echo "  latex     to make LaTeX files, you can set PAPER=a4 or PAPER=letter"
	@echo "  changes   to make an overview over all changed/added/deprecated items"
	@echo "  linkcheck to check all external links for integrity"

clean:
	rm -rf .build/* cli

html:
	mkdir -p .build/html .build/doctrees
	$(SPHINXBUILD) -b html -t online $(ALLSPHINXOPTS) .build/html
	@echo
	@echo "Build finished. The HTML pages are in .build/html."

qthelp:
	mkdir -p .build/qthelp .build/doctrees
	$(SPHINXBUILD) -b customqt $(ALLSPHINXOPTS) .build/qthelp
	@echo
	@echo "Build finished." 

epub:
	mkdir -p .build/qthelp .build/doctrees
	$(SPHINXBUILD) -b myepub $(ALLSPHINXOPTS) .build/epub
	@echo
	@echo "Build finished."



web:
	mkdir -p .build/web .build/doctrees
	$(SPHINXBUILD) -b web $(ALLSPHINXOPTS) .build/web
	@echo
	@echo "Build finished; now you can run"
	@echo "  python -m sphinx.web .build/web"
	@echo "to start the server."

htmlhelp:
	mkdir -p .build/htmlhelp .build/doctrees
	$(SPHINXBUILD) -b htmlhelp $(ALLSPHINXOPTS) .build/htmlhelp
	@echo
	@echo "Build finished; now you can run HTML Help Workshop with the" \
	      ".hhp project file in .build/htmlhelp."

latex:
	mkdir -p .build/latex .build/doctrees
	$(SPHINXBUILD) -b latex $(ALLSPHINXOPTS) .build/latex
	@echo
	@echo "Build finished; the LaTeX files are in .build/latex."
	@echo "Run \`make all-pdf' or \`make all-ps' in that directory to" \
	      "run these through (pdf)latex."

changes:
	mkdir -p .build/changes .build/doctrees
	$(SPHINXBUILD) -b changes $(ALLSPHINXOPTS) .build/changes
	@echo
	@echo "The overview file is in .build/changes."

linkcheck:
	mkdir -p .build/linkcheck .build/doctrees
	$(SPHINXBUILD) -b linkcheck $(ALLSPHINXOPTS) .build/linkcheck
	@echo
	@echo "Link check complete; look for any errors in the above output " \
	      "or in .build/linkcheck/output.txt."
