#!/usr/bin/env python3
#
# randomFill.py: Fill space with random data.
# 2022-03-18: Written by Steven J. DeRose.
#
from __future__ import print_function
import sys
import os
import codecs
import random
import subprocess
from typing import IO

import logging
lg = logging.getLogger("randomFill.py")

def info0(msg:str) -> None:
    if (args.verbose >= 0): lg.info(msg)
def info1(msg:str) -> None:
    if (args.verbose >= 1): lg.info(msg)
def info2(msg:str) -> None:
    if (args.verbose >= 2): lg.info(msg)
def fatal(msg:str) -> None:
    lg.critical(msg); sys.exit()


__metadata__ = {
    "title"        : "randomFill",
    "description"  : "Fill space with random data.",
    "rightsHolder" : "Steven J. DeRose",
    "creator"      : "http://viaf.org/viaf/50334488",
    "type"         : "http://purl.org/dc/dcmitype/Software",
    "language"     : "Python 3.7",
    "created"      : "2022-03-18",
    "modified"     : "2022-03-18",
    "publisher"    : "http://github.com/sderose",
    "license"      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__["modified"]

descr = """
=Name=
    """ +__metadata__["title"] + ": " + __metadata__["description"] + """

=Description=

Generate random data.

This can be used to make a "fuzzing" test file, or to fill up space
(even an entire disk) to clear it.
Does not touch non-empty space (unless there's some unknown bug).

Actually securely cleaing a disk is non-trivial. For spinning disks you may
need to clear multiple times with differing patterns to be sure.

SSDs are much harder to "really" clear, since data moves around to
optimize "wear levelling". Still, filling all empty space should overwrite
all of it, which should do a pretty good job (caveat: the author is not
a cybersecurity expert, and tech also changes -- so do your own homework).

Does not attempt to clean up data sitting in unused parts of allocated
pages, such as just past the end of files that were written by careless
programs, or pages owned by the file system or paging system itself, etc.

Well-known but old methods that
do many alternating writes were designed to be secures across many types of
disks, including very old ones (with very big bits). These are probably
overkill for modern disks, which have much smaller bits for which "echoes" of
prior write are much harder to detect.


==Usage==

    randomFill.py [options] [files]

The most important options are:

* ''--size'' to create only a certain amount of data
* ''--fill'' to keep writing until all available space has been filled
* ''--clear'' so the filled areas are freed again at the end
* ''--pattern''to choose what kind of data to write:
    all 0-bits,
    all 1-bits,
    alternating 0 and 1 bits
    alternating 0 and 255 bytes
    lorem ipsum plain text
    lorem ipsum text encrypted with a given key
    uniform random bytes
    uniform random ASCII characters
    ASCII with English-like character frequencies.
        (1st-order probabilities; may add 2nd or higher some time)


=See also=


=Known bugs and Limitations=


=To do=


=History=

* 2022-03-18: Written by Steven J. DeRose.


=Rights=

Copyright 2022-03-18 by Steven J. DeRose. This work is licensed under a
Creative Commons Attribution-Share-alike 3.0 unported license.
See [http://creativecommons.org/licenses/by-sa/3.0/] for more information.

For the most recent version, see [http://www.derose.net/steve/utilities]
or [https://github.com/sderose].


=Options=
"""

lorem = "".join([
    "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do ",
     "eiusmod tempor incididunt ut labore et dolore magna aliqua. ",
     "Ut enim ad minim veniam, quis nostrud exercitation ullamco ",
     "laboris nisi ut aliquip ex ea commodo consequat. ",
     "Duis aute irure dolor in reprehenderit in voluptate ",
     "velit esse cillum dolore eu fugiat nulla pariatur. ",
     "Excepteur sint occaecat cupidatat non proident, sunt in ",
     "culpa qui officia deserunt mollit anim id est laborum.",
])

# See loremText(type='r'), below.
#
letterFreqsTotal = 0  # setUtilsOption() sets this.
letterFreqs = [ # Rough, from Wikipedia
    ('e',   12702),
    (' ',   17000), # Estimate for non-word chars
    ('t',    9056),
    ('a',    8167),
    ('o',    7507),
    ('i',    6966),
    ('n',    6749),
    ('s',    6327),
    ('h',    6094),
    ('r',    5987),
    ('d',    4253),
    ('l',    4025),
    ('c',    2782),
    ('u',    2758),
    ('m',    2406),
    ('w',    2360),
    ('f',    2228),
    ('g',    2015),
    ('y',    1974),
    ('p',    1929),
    ('b',    1492),
    ('v',     978),
    ('k',     772),
    ('j',     153),
    ('x',     150),
    ('q',      95),
    ('z',      74),
  ]

def randomText1( n:int):
    """Pick characters in accord w/ English first-order frequencies.
    TODO: Swith to GNG data, add punctuation
    """
    buf = ""
    for _i in range(n):
        r = random.randint(1, letterFreqsTotal)
        for tup in letterFreqs:
            r -= tup[1]
            if (r < 1): buf += tup[0]
        buf += ' '
    return buf


###############################################################################
#
def writeOneFile(fh:IO) -> int:
    """Write some data.
    """
    totRecs = 0
    totChars = 0
    while (True):
        if (reusableBuffer is not None):
            rec = reusableBuffer
        else:
            rec = makeRec(args.recsize, args.pattern)
        totRecs += 1
        totChars += len(rec)+1
        try:
            fh.write(rec+"\n")
        except IOError as e:
            lg.warning("Exception writing record %d:\n    %s", totChars, e)
            break
        if (args.tickInterval and (totRecs % args.tickInterval == 0)):
            lg.warning("Wrote record %12d (to char %14d).", totRecs, totChars)
        if (totChars > args.size):
            lg.warning("Hit size limit %d.", args.size)
            break
    return totChars

def makeRec(n:int, pat:str):
    """Don't call this for the "resuable" patterns, which are pre-made.
    """
    if (pat == "lorem"):
        return lorem * (n/len(lorem))

    buf = ""
    for _i in range(n):
        if(pat == "latin0"):
            buf += chr(random.randint(32, 95))
        elif(pat == "english1"):
            buf = randomText1(n)
        #elif(pat == "english2"):
        #elif(pat == "english3"):
        else:
            lg.warning("Unexpected pattern choice '%s'.", pat)
            sys.exit()
    return buf

def makeReusableBuffer(n:int, pat:str) -> (str, bool):
    """If the chosen pattern is fixed, return the requested length of it.
    Otherwise return None, so we know to generate it every time.
    """
    if (pat == "ones"):       return "\x00" * n
    elif(pat == "zeros"):      return "\xFF" * n
    elif(pat == "altBits"):    return "\x55" * n
    elif(pat == "altBytes"):   return "\x00\xFF" * n
    elif(pat == "lorem"):      return "0" * n
    return None


###############################################################################
# Main
#
if __name__ == "__main__":
    dftTarget = "/tmp/randomFill.data"

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
            "--fill", action="store_true",
            help="Keep writing until there's no more space.")
        parser.add_argument(
            "--pattern", type=str, choices=[
                "ones", "zeros", "altBits", "altBytes", "lorem",
                "latin0", "english1", "english2", "english3", ],
            help="What kind of data to write.")
        parser.add_argument(
            "--encrypt", action="store_true",
            help="Whatever the --pattern, encrypt before writing.")
        parser.add_argument(
            "--key", type=str,
            help="With --encrypt, use this as the key.")
        parser.add_argument(
            "--quiet", "-q", action="store_true",
            help="Suppress most messages.")
        parser.add_argument(
            "--recsize", type=anyInt, default=4096,
            help="Put newlines every so often.")
        parser.add_argument(
            "--size", type=anyInt,
            help="Write this much data (hex, octal, or decimal).")
        parser.add_argument(
            "--tickInterval", type=anyInt, default=4096,
            help="Report progress once in a while.")
        parser.add_argument(
            "--verbose", "-v", action="count", default=0,
            help="Add more messages (repeatable).")
        parser.add_argument(
            "--version", action="version", version=__version__,
            help="Display version information, then exit.")

        parser.add_argument(
            "target", type=str, default=dftTarget,
            help="Where to write the data.")

        args0 = parser.parse_args()
        return(args0)


    ###########################################################################
    #
    args = processOptions()

    reusableBuffer = makeReusableBuffer(args.recsize, args.pattern)

    if (not args.fill and not args.size):
        lg.warning("Must specify --fill or --size N.")
        sys.exit(99)
    if (os.path.exists(args.target)):
        lg.warning("Output file '%s' already exists. Exiting.", args.target)
        sys.exit(97)
    try:
        ofh = codecs.open(args.target, "wb")
    except IOError as e0:
        lg.warning("Could not open utput file '%s':\n    %s", args.target, e0)
        sys.exit(96)

    nBytes = writeOneFile(ofh)
    ofh.close()

    if (args.clear):
        subprocess.check_output([ "rm", args.target ])

    print("Done. %d bytes written." % (nBytes))

