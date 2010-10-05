#!/usr/bin/env python

import os
import pprint

try:
    from functools import reduce
except ImportError:
    # Assume we have reduce
    pass

from Cheetah import Parser
from Cheetah import Compiler
from Cheetah import Template

class Analyzer(Parser.Parser):
    def __init__(self, *args, **kwargs):
        self.calls = {}
        super(Analyzer, self).__init__(*args, **kwargs)

    def eatDirective(self):
        directive = self.matchDirective()
        try:
            self.calls[directive] += 1
        except KeyError:
            self.calls[directive] = 1
        super(Analyzer, self).eatDirective()

class AnalysisCompiler(Compiler.ModuleCompiler):
    parserClass = Analyzer


def analyze(source):
    klass = Template.Template.compile(source, compilerClass=AnalysisCompiler)
    return klass._CHEETAH_compilerInstance._parser.calls

def main_file(f):
    fd = open(f, 'r')
    try:
        print u'>>> Analyzing %s' % f
        calls = analyze(fd.read())
        return calls
    finally:
        fd.close()


def _find_templates(directory, suffix):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if not f.endswith(suffix):
                continue
            yield root + os.path.sep + f

def _analyze_templates(iterable):
    for template in iterable:
        yield main_file(template)

def main_dir(opts):
    results = _analyze_templates(_find_templates(opts.dir, opts.suffix))
    totals = {}
    for series in results:
        if not series:
            continue
        for k, v in series.iteritems():
            try:
                totals[k] += v
            except KeyError:
                totals[k] = v
    return totals


def main():
    from optparse import OptionParser
    op = OptionParser()
    op.add_option('-f', '--file', dest='file', default=None,
            help='Specify a single file to analyze')
    op.add_option('-d', '--dir', dest='dir', default=None, 
            help='Specify a directory of templates to analyze')
    op.add_option('--suffix', default='tmpl', dest='suffix', 
            help='Specify a custom template file suffix for the -d option (default: "tmpl")')
    opts, args = op.parse_args()

    if not opts.file and not opts.dir:
        op.print_help()
        return

    results = None
    if opts.file:
        results = main_file(opts.file)
    if opts.dir:
        results = main_dir(opts)

    pprint.pprint(results)


if __name__ == '__main__':
    main()

