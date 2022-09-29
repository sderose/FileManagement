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

* Move git support functions into here, from ''PowerWalk.py''.
* Option to spell out status instead of using single-char codes.
* A non-existent file is not considered to be in any version control
system, even if its directory is in scope for one.


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
    
    
def doOneFile(path:str) -> (VCS_Type, gitStatus):
    """Read and deal with one individual file.
    """
    if (not os.path.exists(path)):            # Exists at all?
        return VCS_Type.NONE, gitStatus.NO_FILE
    rc = getGitStatus(path)
    if (rc != gitStatus.NOT_MINE):            # In git?
        return VCS_Type.Git, rc
    rc = getMercurialStatus(path)
    if (rc != gitStatus.NOT_MINE):            # In Mercurial?
        return VCS_Type.Mercurial, rc
    rc = getSVNStatus(path)
    if (rc != gitStatus.NOT_MINE):            # In SVN?
        return VCS_Type.SVN, rc
    return VCS_Type.NONE, gitStatus.ERROR


###############################################################################
#
class gitStatus(Enum):
    # Most of the symbols are what you get from 'git status --porcelain'....
    # (exceptions: E, \\u2205, X, =.
    # git also uses a second column with sub-codes... And submodules are special.
    #
    ERROR		= "E"
    NO_FILE     = "\u2205"  # EMPTY SET symbol
    
    NOT_MINE    = "X"       # Not in this VCS (cf UNTRACKED) TODO: SVN "X" = "present b/c of externals"

    UNTRACKED	= "?"
    IGNORED		= "!"       # TODO: vs. SVN "I"
    UNMODIFIED  = "="       # TODO: vs. SVN "C" = 'clean'; " " in git
    MODIFIED	= "M"
    ADDED		= "A"
    DELETED		= "D"       # TODO: vs. Mercurial "R" = removed
    RENAMED		= "R"       # TODO: SVN "R" = 'replaced'
    COPIED		= "C"       # TODO: SVN "C" = 'conflict'
    UNMERGED	= "U"

    #             "~"       # TODO: SVN "~" = 'changed type'

def getGitStatus(path:str) -> gitStatus:
    """See what sort of git state we're in (see `git status --help` for --porcelain).
    NOTE: It outputs "" for untracked and unchanged files. Some relevant options:
        -uall  -- show untracked
        --ignored=matching
        
    """
    # See if we're even in a git repo
    try:
        gitDir = check_output("git rev-parse --show-toplevel 2>/dev/null", shell=True)
    except CalledProcessError as e:
        return gitStatus.NOT_GIT
    try:
        tokens = [ "git", "status", "--porcelain", "--ignored=matching", path ]
        buf = str(check_output(tokens))
        buf0 = buf[0]
        if (args.verbose): lg.info("status response length %d, buf0 '%s'" % (len(buf), buf0))
    except CalledProcessError:
        if (args.verbose): lg.info("CalledProcessError")
        return gitStatus.NOT_MINE
    except IndexError:
        if (args.verbose): lg.info("IndexError")
        return gitStatus.UNMODIFIED  # TODO: Check if this is always right
    if (buf0 == " "):
        if (args.verbose): lg.info("Found space")
        return gitStatus.UNMODIFIED
    if (buf0 in "MADRCU?!"): 
        if (args.verbose): lg.info("Found code '%s'" % (buf9))
        return gitStatus(buf0)
    warn(0, "Unknown code '%s' from git status for '%s'." % (buf0, path))
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
            "--longStat", action="store_true",
            help="Show words for file status, not just single characters.")
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
        vcs, status = doOneFile(path0)
        if (args.longStat):
            print("%-12s %-12s %s" % (vcs.name, status.name, path0))
        else:
            print("%-12s %-3s %s" % (vcs.name, status.value, path0))
        
    if (not args.quiet):
        lg.info("versionStatus.py: Done")
