#!/usr/bin/env python
# coding: utf-8

'''
    lmake
    ~~~~~~~~~

    Python module for building latex projects.
'''

from __future__ import with_statement

from itertools import chain
from subprocess import Popen, call, PIPE

import argparse
import codecs
import glob
import logging
import os
import re
import shutil
import sys
import time


__author__ = 'Marc Schlaich. Modified by Shrirang Mare.'
__version__ = '0.6'
__license__ = 'MIT'

BIB_PATTERN = re.compile(r'\\bibdata\{(.*)\}')
CITE_PATTERN = re.compile(r'\\citation\{(.*)\}')
BIBCITE_PATTERN = re.compile(r'\\bibcite\{(.*)\}\{(.*)\}')
BIBENTRY_PATTERN = re.compile(r'@.*\{(.*),\s')
# TODO simplify error pattern
ERROR_PATTTERN = re.compile(r'(?:^! (.*\nl\..*)$)|(?:^! (.*)$)|'
                            '(No pages of output.)', re.M)
LATEX_RERUN_PATTERNS = [re.compile(pattr) for pattr in
                        [r'LaTeX Warning: Reference .* undefined',
                         r'LaTeX Warning: There were undefined references\.',
                         r'LaTeX Warning: Label\(s\) may have changed\.',
                         r'No file .*(\.toc|\.lof)\.']]
TEXLIPSE_MAIN_PATTERN = re.compile(r'^mainTexFile=(.*)(?:\.tex)$', re.M)

LATEX_CMD = "pdflatex"
# TODO: other flags to consider: -shell-escape
LATEX_FLAGS = "--synctex=1 -halt-on-error"
NO_LATEX_ERROR = (
    'Could not run command "%s". '
    'Is your latex distribution under your PATH?'
)

logging.basicConfig(level=logging.INFO)

def run_shell_command(cmd):
    """Run a shell command and return output and error log."""

    p = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if sys.version_info[0] == 3:
        out = out.decode('utf-8')
        err = err.decode('utf-8')
    return out.strip(), err


def latex_run(root):
    '''
    Start latex run.

    Arguments:
        root: string. name of main .tex file. with or without .tex ext
    '''
    logging.info('Running %s...' % LATEX_CMD)
    cmd = "%s %s %s.tex" % (LATEX_CMD, LATEX_FLAGS, root)
    try:
        with open(os.devnull, 'w') as null:
            Popen(cmd.split(), stdout=null, stderr=null).wait()
    except OSError:
        logging.error(NO_LATEX_ERROR % LATEX_CMD)
        sys.exit(1)
    check_errors(root)


def bibtex_run(root):
    '''
    Start bibtex run.
    '''
    logging.info('Running bibtex...')
    try:
        with open(os.devnull, 'w') as null:
            Popen(['bibtex', root], stdout=null).wait()
    except OSError:
        logging.error(NO_LATEX_ERROR % 'bibtex')
        sys.exit(1)
    check_errors(root)


def check_errors(root):
    '''
    Check if errors occured during a latex run by
    scanning the output.

    Arguments:
        root: string. The root .tex file.
        out: output
    '''
    fname = '%s.log' % root
    with codecs.open(fname, 'r', 'utf-8', 'replace') as fobj:
        output = fobj.read()
    errors = ERROR_PATTTERN.findall(output)
    # "errors" is a list of tuples
    if errors:
        logging.error("Error compiling.")
        # do not output lines from main.log contain the memory usage.
        # the relevant error log is before this line.
        i = output.find('Here is how much of')
        lines = output[:i].split('\n')
        logging.error("Last few lines of %s.log: \n%s" % (root, '\n'.join(lines[-20:])))
        logging.error("See %s.log for deatils" % root)
        # logging.error('\n'.join(
        #     [error.replace('\r', '').strip() for error
        #      in chain(*errors) if error.strip()]))

        # logging.error('! See "%s.log" for details.' % root)
        # logging.error('! Exiting...')
        sys.exit(1)

def main():

    parser = argparse.ArgumentParser(description = "Latex python based make file.")
    parser.add_argument('-c', '--clean', action='store_true', default=False, help="clean all temporary files after converting")
    parser.add_argument('--submit', action='store_true', default=False, help="Generate SUBMIT version. By default generates in draft mode.")
    parser.add_argument('--dspace', action='store_true', default=False, help="Use double space. By default uses single space.")
    parser.add_argument('--no-view', dest='view', action='store_false', default=True, help="Do not open PDF.")
    parser.add_argument('--root', type=str, default='main.tex', help="Main (also called root) .tex file. Default: main.tex")
    args = parser.parse_args()


    if not args.root.endswith('.tex'):
        args.root = args.root + '.tex'

    if args.clean:
        patterns = ["*.aux", "*.out", "*.bbl", "*.blg", "*.log", "*.pdfsync", "*.synctex.gz", "*.stdout", "main.pdf"]
        for pattern in patterns:
            for tmpfile in glob.glob(pattern):
                os.remove(tmpfile)
        return


    # get git revision and status before you modify root_tex
    git_revision, err = run_shell_command("git rev-parse --short HEAD")
    git_status, err = run_shell_command("git status --porcelain .")
    git_branch, err = run_shell_command('git rev-parse --abbrev-ref HEAD')
    uncommitted_files = [t for t in git_status.strip().split('\n') if t != '']

    outpdf = args.root.replace('.tex', '.pdf')

    # During lmake build we modify the root tex file
    # Work on a tmp copy of the root file so that we do not modify the
    # actual root file.
    root_tex = 'tmp.' + args.root
    root = root_tex.replace('.tex', '')

    root_fp = open(root_tex, 'w')
    for line in open(args.root, 'r'):
        if line.find('LMAKE-GIT-COMMIT') >= 0:
            revision_str = '%s. branch: %s' % (git_revision, git_branch)
            line = line.replace('LMAKE-GIT-COMMIT', revision_str)

        elif line.find('LMAKE-GIT-STATUS') >= 0:
            git_status_str = "git status. Uncommited files: %d\n" % (len(uncommitted_files))
            if len(uncommitted_files):
                git_status_str += "\\begin{verbatim}%s\\end{verbatim}" % git_status
            line = line.replace('LMAKE-GIT-STATUS', git_status_str)

        elif args.dspace and line.find('LMAKE-DOUBLE-SPACED') > 0:
            line = line.strip()
            assert(line.startswith('%'))
            line = line[1:] + '\n'

        elif args.submit and line.find('LMAKE-SUBMIT') > 0:
            line = line.strip()
            assert(line.startswith('%'))
            line = line[1:] + '\n'


        root_fp.write(line)
    root_fp.close()

    # Build pdf
    latex_run(root)
    latex_run(root)
    bibtex_run(root)
    latex_run(root)

    # Rename the outputfile to match the given root name.
    shutil.move('%s.pdf' % root, outpdf)

    if args.view:
        call(['open', outpdf])


if __name__ == '__main__':
    main()
