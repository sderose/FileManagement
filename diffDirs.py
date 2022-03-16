#!/usr/bin/env python3
#
# diffDirs: Quick and dirty compare for directory trees.
# 2014-06-27: Written by Steven J. DeRose.
#
# pylint: disable=W0603
#
import sys
import os
import re
import argparse
import subprocess
import stat

from alogging import ALogger
from PowerWalk import isHidden, isBackup, isGenerated

__metadata__ = {
    'title'        : "diffDirs",
    'description'  : "Quick and dirty compare for directory trees.",
    'rightsHolder' : "Steven J. DeRose",
    'creator'      : "http://viaf.org/viaf/50334488",
    'type'         : "http://purl.org/dc/dcmitype/Software",
    'language'     : "Python 3.7",
    'created'      : "2014-06-27",
    'modified'     : "2020-09-23",
    'publisher'    : "http://github.com/sderose",
    'license'      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__['modified']

descr = """
=Usage=

[unfinished]

This compares 2 directories, showing their differences on a file-by-file
basis. Prefers a wide window. By default, ignores backup files, invisible files,
and some generated files (like .pyc).

Similar to `diff -r`, but more informative and perhaps faster.

There are options to compare size, data, md5 checksum, and actual content;
and to show the first differing lines.


=Known bugs and limitations=

Not smart about case differences in filenames on MacOSX.

Doesn't do anything special for binary files.
See https://stackoverflow.com/questions/1446549/


=Related commands=

`diff`.  My `findDuplicateFiles`.


=History=

* 2014-06-27: Written by Steven J. DeRose.
* 2014-07-09: Add --color, --comment, --nil, --prefixWidth, -r, -y, ignoreExprs.
* 2014-07-17: Add ignored 1v2, total1, total2.
* 2014-07-19: Fix md5. Add --report-identical-files. --permissions.
* 2018-10-16: Cleanup and refactor. Add MarkupHelpFormatter, --diffq.
* 2020-06-10: Switch to PowerWalk.isBackup. New layout.
* 2020-08-21: Fix handling of binary files and EOF conditions.
* 2020-09-23: Drop sjdUtils.


=To do=

* Sync w/ `findDuplicateFiles`, and move normalizations to `sjdUtils`.
* Complain about links, zeros.
* Options: ignore blank lines, --ignore-file-name-case, ctime, atime
* Options:  svn/git status, first diff line?
* Option to run preprocesser on files.
* Handle compressed files.
* Add interactive i/f: pause on diff and:
  copy > or < (and warn if newer or larger) (w/ backup options)
  run diff and ask again
* Integrate rest of `PowerWalk`?


=Rights=

Copyright 2014 by Steven J. DeRose.
This work is licensed under a Creative Commons
Attribution-Share Alike 3.0 Unported License. For further information on
this license, see [http://creativecommons.org/licenses/by-sa/3.0].

For the most recent version, see [http://www.derose.net/steve/utilities] or
[https://github.com/sderose].


=Options=
"""

total1 = total2 = missing1 = missing2 = uncheckedDirs = 0
same = differ = ignored1 = ignored2 = comment1 = comment2 = 0


###############################################################################
#
def normalizeXmlSpace(s):  # From sjdUtils.py
    """Reduce runs of space, tab, linefeed, and cr to a single space, and
    strip the same characters off start and end of a string.
    """
    if (s is None): return("")
    s = re.sub(r'\s+',' ', s)
    s = re.sub(r'^ ','', s)
    s = re.sub(r' $','', s)
    return(s)

def pcols(theFile, diffInfo, color1="off", width=0, sep=""):
    """Print a one-line report about a file-difference.
    @param diffInfo: A string of keywords indicating what the difference is:
        SIZE, TIME, PERM(issions), MD5, DIFF(line %d vs %d).
    """
    if (width<=0): width = wid
    theFile = theFile.strip()
    diffInfo = diffInfo.strip()
    ind = "    " * int(lg.MsgGet())
    msg = ind + sep.ljust(args.prefixWidth)
    if (args.color):
        msg += lg.colorize(color1, theFile.ljust(args.nameWidth))
        msg += lg.colorize("red", diffInfo)
    else:
        msg += theFile.ljust(args.nameWidth)
        msg += diffInfo
    lg.vMsg(0, msg)

def stat2print(statValue):
    """Create a printable list of permissions flags, like 'ls -l' has.
    @return: string of letters and hyphens.
    """
    if (len(statValue) != 10):
        raise ValueError("stat2print: arg is not len 10")
    mo = statValue[stat.ST_MODE]
    flags = [ "-" for x in range(10) ]
    if (mo & stat.S_ISDIR): flags[0] = 'd'  # 40000  directory
    if (mo & stat.S_IRUSR): flags[1] = 'r'  # 00400  owner read
    if (mo & stat.S_IWUSR): flags[2] = 'w'  # 00200  owner write
    if (mo & stat.S_IXUSR): flags[3] = 'x'  # 00100  owner execute
    if (mo & stat.S_IRGRP): flags[4] = 'r'  # 00040  group read
    if (mo & stat.S_IWGRP): flags[5] = 'w'  # 00020  group write
    if (mo & stat.S_IXGRP): flags[6] = 'x'  # 00010  group execute
    if (mo & stat.S_IROTH): flags[7] = 'r'  # 00004  others read
    if (mo & stat.S_IWOTH): flags[8] = 'w'  # 00002  others write
    if (mo & stat.S_IXOTH): flags[9] = 'x'  # 00001  others execute
    buf = "".join(flags)
    return(buf)

def firstMismatch(path1, path2):
    """Find the first difference between two files (can ignore comments)
    Return (linenumber1, linenumber2, line1, line2) of first diff.
    NOTE: Only works for text files....
    """
    fh1 = open(path1, 'rb')
    fh2 = open(path2, 'rb')
    recnum1 = recnum2 = 0

    lg.vMsg(2, "Comparing %s..." % (os.path.basename(path1)))
    while (1):
        rec1, nRecs1 = advanceFile(fh1, recnum1)
        recnum1 += nRecs1
        if (rec1 is None):
            return recnum1, recnum2, "", ""
        rec2, nRecs2 = advanceFile(fh2, recnum2)
        recnum2 += nRecs2
        if (rec2 is None):
            return recnum1, recnum2, "", ""

        if (rec1=='' and rec2==''): break

        if (args.b):
            rec1 = normalizeXmlSpace(rec1)
            rec2 = normalizeXmlSpace(rec2)
        if (args.ignoreCase):
            rec1 = rec1.lower()
            rec2 = rec2.lower()
        if (rec1 != rec2):
            return(recnum1, recnum2, rec1, rec2)
    return 0, 0, "", ""

def advanceFile(fh0, recnum):
    """Returns None on decoding error.
    """
    nRecsRead = 0
    while (1):
        try:
            rec = fh0.readline()
        except UnicodeDecodeError as e:
            lg.vMsg(0, "Bad data at record %d: %s" % (recnum+nRecsRead, e))
            return None, nRecsRead
        if (rec == ""): break
        nRecsRead += 1
        if (args.tickInterval and (recnum+nRecsRead) % args.tickInterval == 0):
            lg.vMsg(0, "Record %6d..." % (recnum))
        if (not ignorableLine(rec)): break
    return rec, nRecsRead

def ignorableLine(rec):
    if (re.match(r'^\s*$', rec)): return True
    if (args.comment and re.match(args.comment, rec)): return True
    return False

def filteredListdir(dpath):
    """Remove undesired files from an os.listdir() list.
    """
    ld = set(os.listdir(dpath))
    ld2 = []
    for f in ld:
        if (not args.hidden and isHidden(f)): continue
        if (not args.backups and isBackup(f)): continue
        if (not args.generated and isGenerated(f)): continue
        ld2.append(f)
    return ld2

def compareDirs(path1, path2):
    """Compare two directories, by recursing.
    @return dirsDiffer: 0 if the dirs completely match, else non-zero
    (specifically, the number of differing/missing files found).
    @globals Bumps counters for a bunch of things.
    """
    global total1, total2, missing1, missing2, uncheckedDirs
    p1 = os.path.abspath(path1)
    d1 = filteredListdir(p1)

    p2 = os.path.abspath(path2)
    d2 = filteredListdir(p2)

    dUnion = sorted(list(set(d1).union(set(d2))))

    lg.vMsg(0, "\n***Comparing directories:")
    lg.vMsg(0, "    %s\n    %s\n" % (p1, p2))

    nSubsDifferent = 0
    for curName in dUnion:
        lg.vMsg(1, "Comparing '%s'." % (curName))
        #print("Comparing '%s'." % (curName))
        file1 = os.path.join(path1, curName)
        file2 = os.path.join(path2, curName)
        if (not os.path.exists(file1)):
            lg.vMsg(1, "    Missing from dir 1: " + path1)
            #print("    Missing from dir 1: " + path1)
            missing1 += 1
            nSubsDifferent += 1
        elif (not os.path.exists(file2)):
            lg.vMsg(1, "    Missing from dir 2: " + path1)
            missing2 += 1
            nSubsDifferent += 1
        elif (os.path.isdir(file1) and os.path.isdir(file2)):
            if (args.recursive):
                lg.hMsg(2, "    Descending into %s/" % (curName))
                #lg.MsgPush()
                subDiffs = compareDirs(file1, file2)
                if (subDiffs): nSubsDifferent += 1
                #lg.MsgPop()
            else:
                uncheckedDirs += 1
        elif (os.path.isdir(file1) or os.path.isdir(file2)):
            lg.vMsg(0, "Dir/file mismatch: %s and %s" % (file1, file2))
            nSubsDifferent += 1
        else:
            total1 += 1
            total2 += 1
            fDiff = compareFiles(file1, file2)
            if (fDiff): nSubsDifferent += 1
    return nSubsDifferent

def compareFiles(fp1, fp2):
    """Compare two *files* (not dirs).
    @return isDifferent: 0 if the files completely match, else 1.
    @globals Bumps counters for a bunch of things.
    """
    #global total1, total2, missing1, missing2, uncheckedDirs, ignored1, ignored2,
    global same, differ

    if (os.path.isdir(fp1) or os.path.isdir(fp2)):
        raise ValueError("compareFiles called for a directory.")

    diffLine = ""
    isDifferent = 0

    size1 = os.path.getsize(fp1)
    size2 = os.path.getsize(fp2)
    time1 = os.path.getmtime(fp1)
    time2 = os.path.getmtime(fp2)
    stat1 = stat2 = 'N/A'
    md51 = md52 = 'N/A'

    if (args.size and size1 != size2):
        diffLine += " SIZE"
        isDifferent = True

    if (args.time and time1 != time2):
        diffLine += " TIME"
        isDifferent = True

    if (args.permissions):
        stat1 = stat2print(os.stat(fp1))
        stat2 = stat2print(os.stat(fp2))
        if (stat1 != stat2):
            diffLine += " PERM"
            isDifferent = True

    if (args.md5):
        # Could use hashlib.md5()
        out1 = subprocess.check_output(["md5sum", fp1])
        out2 = subprocess.check_output(["md5sum", fp2])
        md51 = re.sub(r'\s+.*', '', out1)
        md52 = re.sub(r'\s+.*', '', out2)
        if (md51 != md52):
            diffLine += " MD5"
            isDifferent = True

    if (args.diff):
        # Check if they're binary or text...
        #
        lineNum1, lineNum2, rec1, rec2 = firstMismatch(fp1,fp2)
        if (lineNum1):
            diffLine += " DIFF(line %d vs %d)" % (lineNum1,lineNum2)
            isDifferent = True
            if (args.showLines):
                lg.vMsg(0, "    < %s\n    > %s" % (rec1, rec2))
    elif (args.diffq):
        cmd = "diff -q '%s' '%s'" % (fp1,fp2)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        _output, _err = p.communicate()
        p_status = p.wait()
        if (p_status):
            diffLine += " DIFF-Q"
            isDifferent = True

    # Report file difference
    if (args.report_identical_files):
        same += 1
        pcols(fp1, diffInfo='', sep="======")
        if (args.showDiffs):
            fmt = "        size %12d time %-12s md5 %-32s perm %s"
            lg.vMsg(0, fmt % (size1, time1, md51, stat1))
            lg.vMsg(0, fmt % (size2, time2, md52, stat2))
    elif (isDifferent):
        differ += 1
        sep = "!!!!!!"
        color = "red"
        pcols(os.path.basename(fp1), diffLine, color1=color, sep=sep)
        if (args.showDiffs):
            fmt = "        size %10d, time %-20s, md5 %-32s, perm %s"
            lg.vMsg(0, fmt % (size1, time1, md51, stat1))
            lg.vMsg(0, fmt % (size2, time2, md52, stat2))
    else:
        sep = "======"
        color="green"
        same += 1

    return isDifferent


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
            "--all", action='store_true',
            help='Include copy, backup, hidden, and object files.')
        parser.add_argument(
            "-b", action='store_true',
            help='Ignore differences in whitespace.')
        parser.add_argument(
            "--backups", action='store_true',
            help='Include copy and backup files (implied by --all).')
        parser.add_argument(
            "--color", action='store_true', default=False,
            help='Colorize the output.')
        parser.add_argument(
            "--nocolor", action='store_false', dest="color",
            help='Turn off colorizing.')
        parser.add_argument(
            "--comment", "--ignore-matching-lines", type=str, default="",
            help='Ignore lines matching this regex (e.g. "^\\s*#").')
        parser.add_argument(
            "--diff", action='store_true', default=True,
            help='Compare contents (see also --showLines). Default: True.')
        parser.add_argument(
            "--diffq", action='store_true',
            help='Compare contents via system "diff -q".')
        parser.add_argument(
            "--nodiff", action='store_false', dest='diff',
            help='Do NOT compare file contents.')
        parser.add_argument(
            "--generated", action='store_true',
            help='Include generated files, such as .pyc, .DS_Store.')
        parser.add_argument(
            "--hidden", action='store_true',
            help='Include hidden (dot-initial) files (implied by --all).')
        parser.add_argument(
            "--ignoreCase", "-i", action='store_true',
            help='Disregard case distinctions.')
        parser.add_argument(
            "--md5", action='store_true',
            help='Compare file checksums using *nix md5 command.')
        parser.add_argument(
            "--nameWidth", type=int, default=32,
            help='m to reserve for filenames.')
        parser.add_argument(
            "--nil", type=str, default="(NONE)",
            #chr(0xA4)*5,
            help='String to show for missing files.')
        parser.add_argument(
            "--prefixWidth", type=int, default=8,
            help='Columns to reserve for status prefix (=== or !!!...).')
        parser.add_argument(
            "--quiet", "-q", action='store_true',
            help='Suppress most messages.')
        parser.add_argument(
            "-permissions", action='store_true',
            help='Check that permissions match.')
        parser.add_argument(
            "--recursive", "-r", action='store_true',
            help='Descend into subdirectories.')
        parser.add_argument(
            "--report-identical-files", action='store_true',
            help='Just report files that *do* match across dirs.')
        parser.add_argument(
            "--showDiffs", action='store_true',
            help='For each differing file, list size, time, md5, etc.')
        parser.add_argument(
            "--showLines", action='store_true',
            help='Compare file sizes.')
        parser.add_argument(
            "--size", action='store_true', default=True,
            help='Compare file sizes.')
        parser.add_argument(
            "--tickInterval", type=int, default=0,
            help='For long file comparison, show progress / n lines.')
        parser.add_argument(
            "--time", action='store_true',
            help='Compare file times.')
        parser.add_argument(
            "--verbose", "-v", action='count', default=0,
            help='Add more messages (repeatable).')
        parser.add_argument(
            "--version", action='version', version='Version of '+__version__,
            help='Display version information, then exit.')

        parser.add_argument(
            'dirs', type=str, nargs=argparse.REMAINDER,
            help='Path(s) to input dir(s)')
        args0 = parser.parse_args()
        return args0


    ###########################################################################
    # Main
    #
    args = processOptions()

    lg = ALogger(1)

    if (args.all):
        args.backups = args.hidden = True

    if (not args.color):
        args.color = ("USE_COLOR" in os.environ and sys.stderr.isatty())
    lg.setColors(args.color)

    if (not (args.size or args.time or args.md5 or args.diff)):
        lg.vMsg(0, "No file comparisons specified (--size --time --md5 --diff)")

    if ("COLUMNS" in os.environ): wid = os.environ["COLUMNS"]
    else: wid = 80

    totalRecords = 0
    totalFiles = 0

    if ("COLUMNS" in os.environ):
        wid = int(os.environ["COLUMNS"])
    else:
        lg.vMsg(0, "Can't find environment variable COLUMNS -- export it?")
        wid = 80

    if (len(args.dirs) != 2 or
        not os.path.isdir(args.dirs[0]) or
        not os.path.isdir(args.dirs[1])):
        lg.fatal("Specify exactly 2 directories.")

    rc0 = compareDirs(args.dirs[0], args.dirs[1])

    if (not args.quiet):
        lg.info("====Done, rc %d." % (rc0))
        lg.MsgPush()
        lg.vMsg(1, ("Options: b %s, diff %s, i %s, md5 %s,\n" +
                "           permissions %s, r %s, size %s, time %s.") %
                (args.b, args.diff, args.ignoreCase, args.md5,
                 args.permissions, args.recursive, args.size, args.time))
        lg.vMsg(0, "Dirs: %s\n        %s" % (args.dirs[0],  args.dirs[1]))
        lg.pline("Total files from 1:",       total1)
        lg.pline("Total files from 2:",       total2)
        lg.pline("Missing from 1:",           missing1)
        lg.pline("Missing from 2:",           missing2)
        lg.pline("Unchecked nested dirs:",    uncheckedDirs)
        lg.pline("Differing:",                differ)
        lg.pline("Ignored files from 1:",     ignored1)
        lg.pline("Ignored files from 2:",     ignored2)
        if (args.comment != ""):
            lg.pline("Comment lines from 1//*:",  comment1)
            lg.pline("Comment lines from 2//*",   comment2)
        lg.MsgPop()

    sys.exit(0)
