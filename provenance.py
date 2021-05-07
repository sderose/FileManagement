#!/usr/bin/env python
#
# provenance.py: Experiment with supporting file-source tracking.
# 2021-04-27: Written by Steven J. DeRose.
#
import sys
import os
import codecs
import stat
import fcntl
import hashlib
from enum import Enum

from PowerWalk import PowerWalk, PWType


__metadata__ = {
    "title"        : "provenance.py",
    "description"  : "Experiment with supporting file-source tracking.",
    "rightsHolder" : "Steven J. DeRose",
    "creator"      : "http://viaf.org/viaf/50334488",
    "type"         : "http://purl.org/dc/dcmitype/Software",
    "language"     : "Python 3.7",
    "created"      : "2021-04-27",
    "modified"     : "2021-04-27",
    "publisher"    : "http://github.com/sderose",
    "license"      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__["modified"]


descr = """
=Description=

The idea here is to support annoating files with references to where they
"came from". For example:

* a backup copy => what it's a backup of
* a compiled file (object code, PDF, etc) => source
* a new format of a file => source
* an email file => what it replies to
* a moved file to where it was before (save rsync/backup time)

A file identifier includes:
    * a volume guid
    * an inode number
    * a path
    * a version identifier (git commit, etc)
    * a specific time (since all the above can change)
    * a checksum (so you can actually verify if it changes)

A provenance record might also want to record:
    * who did the change
    * when the change happened
    * what tool or command generated the new file
    * a kind of relationship:
        ** backup
        ** mechanical derivation
        ** new version
        ** transformation: port, translation, format conversion, normalization
        ** extracted part of the original (what part?), abridgement
    * A specific claim that this file has no predecessor.
        Some cases involve multiple sources for a given result, which I'm not
tackling to start with:

    * a merge
    * chains of copies

==Usage==

    provenance.py [options] [files]


=Related Commands=


=Known bugs and Limitations=

What about links?


=History=

* 2021-04-27: Written by Steven J. DeRose.


=To do=


=Rights=

Copyright 2021-04-27 by Steven J. DeRose. This work is licensed under a
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
class ChangeType(Enum):
    NEW = 0
    COPY = 10
    MOVE = 20
    ANNOTATE = 30
    MERGE = 40
    SPLIT = 50
    DELETE = 60
    BACKUP = 70
    NEW_VERSION = 100
    NEW_FORMAT = 110
    NEW_LANGUAGE = 120


###############################################################################
#
class ProvenanceEntry:
    def __init__(self, path):
        assert os.path.exists(path)

        self.path = path
        self.normpath = os.path.normpath(path)
        self.abspath = os.path.abspath(path)

        # Just keep the entire stat?
        st = os.stat(path)

        self.data = {
            "dev": st.st_dev,
            "inode": st.st_ino,
            "volumeId": getVolumeId(path, st.st_dev),
            "atime": st.st_atime,
            "btime": st_birthtime,
            "ctime": st.st_ctime,
            "mtime": st.st_mtime,
            "size": st.st_size,
            "csumType": 'sha256',
            "csum": self.dsign(path),
            "gitcommit": ''             # TODO
        }

    def getVolumeId(path, dev):
        with open(path, "rb") as ifh:
            # MacOS
            fcntl.fcntl(ifh, cmd, arg=bytesArg)

    def dsign(self, path):
        m = hashlib.sha256()
        with open(path, "rb") as ifh:
            while buf = ifh.read():
                m.add(buf)
        return m.hexdigest()

    def getGitCommit(path):
        pass

    def tostring(self):
        pass

    def addXAttrs(self, force=False):
        attrName = "provenance"
        buf = os.getxattr(path, attrName)
        if (buf and not force): return False
        os.setxattr(self.path, attrName, self.tostring())
        pass

def showPartitions():
    import psutil
    dps = psutil.disk_partitions()
    for i, dp in enumerate(dps):
        print("\n*** Disk Partion #%d:" % (i))


###############################################################################
# Main
#
if __name__ == "__main__":
    import argparse
    def anyInt(x):
        return int(x, 0)

    def processOptions():
        try:
            from BlockFormatter import BlockFormatter
            parser = argparse.ArgumentParser(
                description=descr, formatter_class=BlockFormatter)
        except ImportError:
            parser = argparse.ArgumentParser(description=descr)

        parser.add_argument(
            "--quiet", "-q", action="store_true",
            help="Suppress most messages.")
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

    if (len(args.files) == 0):
        warning0("provenance.py: No files specified....")
        doOneFile(None)
    else:
        pw = PowerWalk(args.files, open=False, close=False,
            encoding=args.iencoding)
        pw.setOptionsFromArgparse(args)
        for path0, fh0, what0 in pw.traverse():
            if (what0 != PWType.LEAF): continue
            doOneFile(path0)
        if (not args.quiet):
            warning0("provenance.py: Done, %d files.\n" % (pw.getStat("regular")))
