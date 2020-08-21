#!/usr/bin/env python
#
# syncDirs.py: find any of these files that also have a copy among my
# utilities, and report (and optionally update) if they're not identical.
#
from __future__ import print_function
import sys, os
import argparse
import re
#import string
import subprocess
#import codecs
#import PowerWalk

__metadata__ = {
    'title'        : "syncDirs.py",
    'rightsHolder' : "Steven J. DeRose",
    'creator'      : "http://viaf.org/viaf/50334488",
    'type'         : "http://purl.org/dc/dcmitype/Software",
    'language'     : "Python 3.7",
    'created'      : "2018-11-13",
    'modified'     : "2020-06-04",
    'publisher'    : "http://github.com/sderose",
    'license'      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__['modified']

descr = """
=Description=

[Somewhat broken. Works on simple cases, but gets relative paths out of sync]


Check for files that have a (same-name) copy among my
utilities, and see whether they are identical to that normative copy.
Files are found by name, even if their locations relative to the top-level
directories being compared, differ.

==Usage==

    syncDirs.py --baseDir ~/foo /u/xyz/otherDir

will traverse the files under `/u/xyz/otherDir`, and for each one, look for it
anywhere under the baseDir (~/foo):

* If no matching file is found, a warning is displayed.
* If one matching file is found but its relative paths differs,
both relative paths are displayed.
* If more than one such file is found, a list of them is displayed unless `-q`.
* Each one found is `diff`ed against the one in `/u/xyz/otherDir`.


=Related Commands=

My `diffDirs.py`.


=Known bugs and Limitations=

Option to copy any that differ, or move ones that differ in relative path, is not yet implemented.

Should probably have options for better treatment of multiple hits.

Maybe allow C<diff> options like I<-b>, and/or make I<-v> include a full
C<diff> instead of just C<diff -q> status.

=History=

* 2018-11-13: Written by Steven J. DeRose.
* 2020-06-04: New layout and reporting.


=Rights=

Copyright 2015 by Steven J. DeRose. This work is licensed under a Creative Commons
Attribution-Share Alike 3.0 Unported License. For further information on
this license, see [http://creativecommons.org/licenses/by-sa/3.0].

For the most recent version, see [http://www.derose.net/steve/utilities] or
[http://github.com/sderose].

=Options=
"""

def warn(lvl, msg):
    if (args.verbose >= lvl):
        sys.stderr.write(msg+"\n")


###############################################################################
#
def doOneFile(dirpath, filename, top=""):
    """Read and deal with one individual file.
    """
    #warn(1, "dir %s, file %s." % (dirpath, filename))
    path = os.path.join(dirpath, filename)
    expectAt = os.path.join(args.baseDir, filename)

    if (os.path.exists(expectAt)):
        if (not isDifferent(path, expectAt)):
            return False
        warn(0, "Files differ:\n    %s\n    %s" % (path, expectAt))
    else:
        warn(0, "File not at expected path: %s" % (expectAt))
        reportCandidates(dirpath, filename, top=top)

    return True  # Some issue


def isDifferent(f1, f2):
    """Use 'diff' to compare 2 files, and return True if they differ.
    If they're the same, diff itself returns 0 (success).
    If they differ, diff returns non-zero (fail), and Python
    raises CalledProcessError.
    """
    try:
        diffResult = subprocess.check_output([ "diff", "-q", f1, f2])
    except subprocess.CalledProcessError:  # Raised on non-zero exit code
        return True
    return False


def reportCandidates(dirpath, filename, top=""):
    buf = str(subprocess.check_output(
        ["find", args.baseDir, "-name", filename ]), encoding="utf-8")
    if (not buf):
        return 0
    files = buf.strip().split("\n")
    if (len(files) == 0):
        warn(0, "    No candidates found: '%s'" % (filename))
        return 0

    for f in files:
        short = re.sub(args.baseDir, '', f)
        warn(0, "    ??? %s" % (short))
    return len(files)


###############################################################################
###############################################################################
# Main
#
if __name__ == "__main__":
    def processOptions():
        try:
            from BlockFormatter import BlockFormatter
            parser = argparse.ArgumentParser(
                description=descr, formatter_class=BlockFormatter)
        except ImportError:
            parser = argparse.ArgumentParser(description=descr)

        parser.add_argument(
            "--baseDir",          type=str,
            help='Look for copies under this directory.')
        parser.add_argument(
            "--hidden",           action='store_true',
            help='Include hidden (.-initial) files.')
        parser.add_argument(
            "--ignore",           type=str, action='append',
            default=[ "README.txt" ],
            help='Ignore this filename even if on command line.')
        parser.add_argument(
            "--quiet", "-q",      action='store_true',
            help='Suppress most messages.')
        parser.add_argument(
            "--recursive",        action='store_true',
            help='Descend into subdirectories.')
        parser.add_argument(
            "--verbose", "-v",    action='count',       default=0,
            help='Add more messages (repeatable).')
        parser.add_argument(
            "--version", action='version', version=__version__,
            help='Display version information, then exit.')

        parser.add_argument(
            'files',             type=str,
            nargs=argparse.REMAINDER,
            help='Path(s) to input file(s)')

        args0 = parser.parse_args()
        if (not args0.baseDir):
            dftEnvVar = 'sjdUtilsDir'
            if (dftEnvVar in os.environ):
                args0.baseDir = os.environ[dftEnvVar]
                if (args0.verbose):
                    print("Defaulting --baseDir to $%s: '%s' ."
                        % (dftEnvVar, args0.baseDir))
            else:
                print("No --baseDir given, and no env var $%s." % (dftEnvVar))
                sys.exit()

        return(args0)

    ###########################################################################
    #
    args = processOptions()

    if (len(args.files) == 0):
        warn(0, "No directory specified....\n")
        sys.exit()
    topDir = args.files[0]
    if (not os.path.isdir(topDir)):
        warn(0, "Directory not found: %s\n" % (topDir))
        sys.exit()

    nDiffsTotal = 0;
    nSameTotal = 0
    for dirpath, dirnames, filenames in os.walk(topDir):
        if (not args.hidden):
            filenames = [f for f in filenames if not f[0] == '.']
            dirnames[:] = [d for d in dirnames if not d[0] == '.']
            dirnames[:] = [d for d in dirnames if not d == '__pycache__']
        warn(0, "*** At dir %s" % (dirpath))
        if (0):
            for dirname in dirnames:
                fullPath = os.path.join(dirpath, dirname)
                print("    Subdir: %s" % (dirname))
        nDiffsHere = 0; nSameHere = 0
        for filename in filenames:
            fullPath = os.path.join(dirpath, filename)
            if (filename in args.ignore): continue
            if (doOneFile(dirpath, filename, top=topDir)):
                nDiffsHere += 1
            else:
                nSameHere += 1
        print("    [ %d files different, %d the same ]"
            % (nDiffsHere, nSameHere))
        nDiffsTotal += nDiffsHere;
        nSameTotal += nSameHere

    print("[ total: %d files different, %d the same ]"
        % (nDiffsTotal, nSameTotal))

