#!/usr/bin/env python3
#
# versionStatus.py: Figure out what VCS a file belongs to, if any.
# 2022-09-29: Written by Steven J. DeRose.
#
import sys
import os
from enum import Enum
from subprocess import check_output, CalledProcessError
#from collections import defaultdict, namedtuple
#from typing import IO, Dict, List, Union
import logging
lg = logging.getLogger()

from PowerWalk import getGitStatus, gitStatus

__metadata__ = {
    "title"        : "versionStatus.py",
    "description"  : "Figure out what VCS a file belongs to, if any.",
    "rightsHolder" : "Steven J. DeRose",
    "creator"      : "http://viaf.org/viaf/50334488",
    "type"         : "http://purl.org/dc/dcmitype/Software",
    "language"     : "Python 3.9",
    "created"      : "2022-09-29",
    "modified"     : "2022-09-29",
    "publisher"    : "http://github.com/sderose",
    "license"      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__["modified"]

descr = """
=Name=
    """ +__metadata__["title"] + ": " + __metadata__["description"] + """


=Description=

Given a file or directory, see if it's under version control, and what system,
and what state.

Returns or prints the particular VCS (as a VCS_Type Enum), and if it know, a
git-based file status (as a ''gitStatus'' Enum).

    
I'd also like to return the file status, but that's trickier because models differ.
For now, I'm only supporting git statuses, for which the Enum ''gitStatus''.
    

==Usage==

    versionStatus.py [options] [files]


=See also=

[https://en.wikipedia.org/wiki/List_of_version-control_software]

My 'backup', which has slight knowledge of git states.

My 'PowerWalk.py', which provides getGitStatus().


=Known bugs and Limitations=

There are very many more versioning systems out there. I've only done a few.
If you'd like to add some, feel free, and send me the patch.


=To do=

Move git support functions into here, from ''PowerWalk.py''.


=History=

* 2022-09-29: Written by Steven J. DeRose.


=Rights=

Copyright 2022-09-29 by Steven J. DeRose. This work is licensed under a
Creative Commons Attribution-Share-alike 3.0 unported license.
See [http://creativecommons.org/licenses/by-sa/3.0/] for more information.

For the most recent version, see [http://www.derose.net/steve/utilities]
or [https://github.com/sderose].


=Options=
"""


###############################################################################
#
class VCS_Type(Enum):
    """An Enum of version-control systems, based on 
    https://en.wikipedia.org/wiki/List_of_version-control_software.
    I haven't list proprietary ones, but wouldn't mind adding them.
    """
    NONE        = 0

    # Local
    RCS         = 1
    SCCS        = 2

    # Client-server
    CVS         = 11
    SVN         = 12  ##
    Vesta       = 13    
    
    # Open-source distribute
    ArX		    = 101
    Bazaar		= 102
    BitKeeper	= 103
    Darcs		= 104
    DCVS		= 105
    Fossil		= 106
    Git		    = 107  ##
    GNU_arch    = 108
    Mercurial	= 109  ##
    Monotone	= 110
    Perforce    = 111
    Pijul		= 112    
    
    
def doOneFile(path:str) -> gitStatus:
    """Read and deal with one individual file.
    """
    if (not os.path.exists(path)):                      # Exists at all?
        return gitStatus.NO_FILE
    rc = getGitStatus(path)
    if (rc != gitStatus.NOT_MINE):            # In git?
        return rc
    rc = getMercurialStatus(path)
    if (rc != gitStatus.NOT_MINE):            # In Mercurial?
        return rc
    rc = getSVNStatus(path)
    if (rc != gitStatus.NOT_MINE):            # In SVN?
        return rc
    return gitStatus.ERROR

def getMercurialStatus(path):
    """Really don't know how this behaves...
    See https://book.mercurial-scm.org/read/app-svn.html?highlight=status
    See https://lists.mercurial-scm.org/pipermail/mercurial/2014-March/046784.html
       M = modified
       A = added
       R = removed
       C = clean
       ! = missing (deleted by non-hg command, but still tracked)
       ? = not tracked
       I = ignored
         = origin of the previous file listed as A (added)
        
    """
    try:
        rc = check_output([ "hg", "status", path ])
    except CalledProcessError:
        return gitStatus.ERROR
    return rc[0]
    
def getSVNStatus(path):
    """Really don't know how this behaves...
    See https://svnbook.red-bean.com/en/1.8/svn.ref.svn.c.status.html
        ' ' = No modifications.
        'A' = Item is scheduled for addition.
        'D' = Item is scheduled for deletion.
        'M' = Item has been modified.
        'R' = Item has been replaced in your working copy. Was scheduled for deletion, 
            and then a new file with the same name was scheduled for addition in its place.
        'C' = The contents conflict with updates received from the repository.
        'X' = Item is present because of an externals definition.
        'I' = Item is being ignored
        '?' = Item is not under version control.
        '!' = Item is missing (e.g., you moved or deleted it without using svn).
        '~' = Item is versioned as one kind of object (file, directory, link), 
            but has been replaced by a different kind of object.
    """
    try:
        rc = check_output([ "svn", "status", path ])
    except CalledProcessError:
        return gitStatus.ERROR
    return rc[0]
    
    
###############################################################################
# Main
#
if __name__ == "__main__":
    import argparse
    def anyInt(x:str) -> int:
        return int(x, 0)

    def processOptions() -> argparse.Namespace:
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
            "--recursive", action="store_true",
            help="Descend into subdirectories.")
        parser.add_argument(
            "--unicode", action="store_const", dest="iencoding",
            const="utf8", help="Assume utf-8 for input files.")
        parser.add_argument(
            "--verbose", "-v", action="count", default=0,
            help="Add more messages (repeatable).")
        parser.add_argument(
            "--version", action="version", version=__version__,
            help="Display version information, then exit.")

        parser.add_argument(
            "files", type=str, nargs=argparse.REMAINDER,
            help="Path(s) to input file(s)")

        args0 = parser.parse_args()
        #if (args0.verbose): lg.setVerbose(args0.verbose)
        return(args0)


    ###########################################################################
    #
    args = processOptions()

    if (len(args.files) == 0):
        lg.info("versionStatus.py: No files specified....")
        sys.exit()

    for path0 in args.files:
        doOneFile(path0)
    if (not args.quiet):
        lg.info("versionStatus.py: Done")
