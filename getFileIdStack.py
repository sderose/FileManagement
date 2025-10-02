#!/usr/bin/env python3
#
# getFileIdStack.py: Show inode, partition id, volume id, etc.
# 2021-06-14: Written by Steven J. DeRose.
#
import sys
import os
import re
from subprocess import check_output
from PowerWalk import PowerWalk, PWType

__metadata__ = {
    "title"        : "getFileIdStack",
    "description"  : "Show inode, partition id, volume id, etc.",
    "rightsHolder" : "Steven J. DeRose",
    "creator"      : "http://viaf.org/viaf/50334488",
    "type"         : "http://purl.org/dc/dcmitype/Software",
    "language"     : "Python 3.7",
    "created"      : "2021-06-14",
    "modified"     : "2021-06-14",
    "publisher"    : "http://github.com/sderose",
    "license"      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__["modified"]


descr = """
=Description=

==Usage==

    getFileIdStack.py [options] [files]

Show the inode, partition id, volume id, hostid, given a file.


=Related Commands=


=Known bugs and Limitations=


=History=

* 2021-06-14: Written by Steven J. DeRose.


=To do=


=Rights=

Copyright 2021-06-14 by Steven J. DeRose. This work is licensed under a
Creative Commons Attribution-Share-alike 3.0 unported license.
See [http://creativecommons.org/licenses/by-sa/3.0/ for more information].

For the most recent version, see [http://www.derose.net/steve/utilities]
or [https://github.com/sderose].


=Options=
"""

def log(lvl, msg):
    if (args.verbose >= lvl): sys.stderr.write(msg + "\n")
def warning0(msg): log(0, msg)
def warning1(msg): log(1, msg)
def warning2(msg): log(2, msg)
def fatal(msg): log(0, msg); sys.exit()
warn = log


###############################################################################
#
def doOneFile(path):
    """Read and deal with one individual file.
    """
    print("******* %s" % (path))
    if (not os.path.exists(path)):
        print("    File does not exist.")
        return 0
    st = os.stat(path)
    ino = st.ST_INO
    pline("Inode", ino)

    # Figure out which device the file is on
    raw = check_output([ "df", "-P", path ])
    fdata = re.split(r"\n", raw)[-1]
    fsys = re.sub(r" .*", "", fdata)
    assert fsys.startswith("/dev")
    pline("On device", fsys)

    raw = check_output([ "diskutil", "info", fsys ])
    props = {}
    for rec in raw.split("\n"):
        if (not rec.strip()): continue
        mat = re.match(r"\s*([^:]+)\s*(.*)", rec)
        if (not mat): continue
        props[mat.group(1)] = mat.group(2)
    pline("Volume UUID", props["Volume UUID"])
    pline("Disk / Partition UUID", props["Disk / Partition UUID"])

    pline("Host Mac ID", getHostID())

def getHostID():
    raw = check_output([ "ifconfig", "en0" ])
    fdata = re.split(r"\n", raw)[-1]
    mat = re.search(r"^\s*ether (.*)", fdata, flags=re.M)
    if (mat): return mat.group(1)
    return ""

def pline(k, v):
    print("    %20s %12s" % (k, v))


###############################################################################
# Main
#
if __name__ == "__main__":
    import argparse

    def processOptions():
        try:
            from BlockFormatter import BlockFormatter
            parser = argparse.ArgumentParser(
                description=descr, formatter_class=BlockFormatter)
        except ImportError:
            parser = argparse.ArgumentParser(description=descr)

        parser.add_argument(
            "--iencoding", "--input-encoding", type=str, metavar="E", default="utf-8",
            help="Assume this character coding for input. Default: utf-8.")
        parser.add_argument(
            "--ignoreCase", "--ignore-case", "-i", action="store_true",
            help="Disregard case distinctions.")
        parser.add_argument(
            "--oencoding", "--output-encoding", type=str, metavar="E", default="utf-8",
            help="Use this character coding for output. Default: iencoding.")
        parser.add_argument(
            "--quiet", "-q", action="store_true",
            help="Suppress most messages.")
        parser.add_argument(
            "--unicode", action="store_const", dest="iencoding",
            const="utf8", help="Assume utf-8 for input files.")
        parser.add_argument(
            "--verbose", "-v", action="count", default=0,
            help="Add more messages (repeatable).")
        parser.add_argument(
            "--version", action="version", version=__version__,
            help="Display version information, then exit.")

        PowerWalk.addOptionsToArgparse(parser)

        parser.add_argument(
            "files", type=str,
            nargs=argparse.REMAINDER,
            help="Path(s) to input file(s)")

        args0 = parser.parse_args()
        return(args0)


    ###########################################################################
    #
    args = processOptions()
    if (args.iencoding and not args.oencoding):
        args.oencoding = args.iencoding
    if (args.oencoding):
        sys.stdout.reconfigure(encoding="utf-8")  # 3.7+

    if (len(args.files) == 0):
        warning0("getFileIdStack.py: No files specified....")
        doOneFile(None)
    else:
        pw = PowerWalk(args.files, open=False, close=False,
            encoding=args.iencoding)
        pw.applyOptionsFromArgparse(args)
        for path0, fh0, what0 in pw.traverse():
            if (what0 != PWType.LEAF): continue
            doOneFile(path0)
        if (not args.quiet):
            warning0("getFileIdStack.py: Done, %d files.\n" % (pw.getStat("regular")))
