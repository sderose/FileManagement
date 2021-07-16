#!/usr/bin/env python
#
# grepMail.py: Search the hard way for emails.
#
# 2021-07-15: Written by Steven J. DeRose.
#
from __future__ import print_function
import sys
import codecs
import re
import datetime
import time

from PowerWalk import PowerWalk, PWType
from alogging import ALogger
lg = ALogger(1)

__metadata__ = {
    "title"        : "grepMail.py",
    "description"  : "Search the hard way for emails.",
    "rightsHolder" : "Steven J. DeRose",
    "creator"      : "http://viaf.org/viaf/50334488",
    "type"         : "http://purl.org/dc/dcmitype/Software",
    "language"     : "Python 3.7",
    "created"      : "2021-07-15",
    "modified"     : "2021-07-15",
    "publisher"    : "http://github.com/sderose",
    "license"      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__["modified"]

descr = """
=Description=

Search a diretory subtree for emails. Mainly for when you've got backups, archives,
copies, etc. that aren't indexed by your email client itself (or Spotlight).

You can search by the main fields.

Content search is not yet implemented.


==Usage==

    grepMail.py [options] [files]

Search directory subtree(s) for emails.

* A way to configure where to search

* Extension .emlx, .mbox, etc.
* Date range
* Subject regex
* Re/Few/not
* From
* To

Actions:

* Report the path
* Show the header
* Open with your choice of app
* Reset filetime to mime time?
* Copy main fields to extended attributes.


=Known bugs and Limitations

--mintime and --maxtime must be like:

    "Fri, 16 Aug 2019 13:40:16 +0000 (UTC)"  <-- strptime can't seem to do.
    "Thu, 29 Aug 2019 15:14:23 +0000"
    "Fri, 09 Aug 2019 13:36:08 -0700"
    "Wed, 7 Aug 2019 11:00:23 -0400"
    "Fri, 30 Aug 2019 00:22:39 +0000"
    "9 Aug 2019 22:26:43 -0400"
    "Thu 29 Aug 2019 15:14:23 +0000"

The last one is like ctime(). But this really needs to take ISO 8601 times,
including truncation.


=Related Commands=

[https://docs.python.org/3/library/email.parser.html]

=Known bugs and Limitations=


=To do=

Move date/time option-handling into `argparsePP.py`.


=History=

* 2021-07-15: Written by Steven J. DeRose.


=Rights=

Copyright 2021-07-15 by Steven J. DeRose. This work is licensed under a
Creative Commons Attribution-Share-alike 3.0 unported license.
See [http://creativecommons.org/licenses/by-sa/3.0/] for more information.

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

# MIME header fields we don't care about.
discardList = [
    #"Content-Type",
    "Content-Transfer-Encoding",
    #"Subject",
    #"DATE",
    #"Message-ID",
    #"From",
    "MIME-Version",
    #"To",
    "X-Universally-Unique-Identifier",
    "References",
    "Received",
    #"In-Reply-To",
    "Authentication-Results",
    "X-Smtp-Server",
    "Content-Disposition",
    "X-Apple-Content-Length",
    #"Cc",
    "Return-Path",
    "Received-SPF",
    #"Original-recipient",
    "DKIM-Signature",
    "X-MANTSH",
    "X-CLX-Shades",
    "x-dmarc-info",
    "x-dmarc-policy",
    "Content-ID",
    "X-Uniform-Type-Identifier",
    "X-Proofpoint-Virus-Version",
    #"Bcc",
    "X-ICL-INFO",
]

###############################################################################
#
def readMimeHeader(ifh, discards=None, discardX=True):
    if (discards is None): discards = {}
    rec = ifh.readline()
    if (re.match(r"\d+\s*$", rec)):  # Apple mail hack
        rec = ifh.readline()
    fields = {}
    curKey = ""
    curBuf = ""
    while (rec != ""):
        if (rec.strip() == ""):
            break
        mat = re.match(r"^([-\w]+):\s*(.*)", rec)
        if (mat):
            if (curBuf and curKey and curKey not in discards and
                (not discardX or not curKey.lower().startswith("X-"))):
                fields[curKey] = curBuf
            curKey = mat.group(1)
            curBuf = mat.group(2)
        elif (re.match(r"^\s", rec)):
            curBuf += rec
        else:
            raise ValueError("unparseable line in MIME header: %s" % (rec))
        rec = ifh.readline()

    if (curBuf and curKey and curBuf not in discards):
        fields[curKey] = curBuf
    return fields

def scanContent(ifh, expr:str) -> bool:
    """Compile first, with args.ignorecase.
    TODO: Make --content repeatable for AND.
    """
    for rec in ifh.readlines():
        if (re.search(expr, rec)): return True
    return False

def doOneFile(path):
    """Read and deal with one individual file.
    """
    try:
        fh = codecs.open(path, "rb", encoding=args.iencoding)
    except IOError as e:
        warning0("Cannot open '%s':\n    %s" % (path, e))
        return 0

    fields = readMimeHeader(fh, discards=discardList)
    for k, v in fields.items():
        print("Header field '%s' = '%s'" % (k, v))

    #print(lg.formatRec(msgObj))
    if (fails(args.subject, fields, "Subject")):
        return False
    if (fails(args.fr, fields, "From")):
        return False
    if (fails(args.to, fields, "To")):
        return False
    if (fails(args.recip, fields, "To") and
        fails(args.recip, fields, "Cc") and
        fails(args.recip, fields, "Bcc")):
        return False
    if (args.mindate or args.maxdate):
        mailDate = parseMimeTime(fields["Date"])
        if (mailDate<args.umindate or mailDate>args.umaxdate):
            return False

    if (args.content):
        if (not scanContent(fh, args.content)): return False

    fh.close()
    return True

# Date formats such as seen in Apple Mail .emlx files
tformats = [
    "%a, %d %b %Y %H:%M:%S %z",     # Sat, 25 Jan 2020 12:19:49 -0600
    "%a, %d %b %Y %H:%M:%S %Z",     # Sat, 25 Jan 2020 12:19:49 (UTC)
    "%a, %d %b %Y %H:%M:%S",        # Sat, 25 Jan 2020 12:19:49
    "%a %b %d %H:%M:%S %Y",         # Sun Jun 20 23:21:05 1993 (per ctime)
    "%d %b %Y %H:%M:%S %z",         # 25 Jan 2020 16:10:05 -0600
    "%d %b %Y %H:%M:%S %Z",         # 25 Jan 2020 16:10:05
]

def fails(expr, fields, fieldName):
    """Return True iff the user gave a constraint in expr, for the fieldName;
    and the fieldName either doesn't exist or doesn't match.
    """
    if (not expr): return False
    if (fieldName not in fields): return True
    if (args.ignorecase):
        return not re.match(fields[fieldName], expr, re.I)
    else:
        return not re.match(fields[fieldName], expr)

def parseMimeTime(s:str) -> int:
    """Parse a MIME "Date" into a tm_struct, then convert to Unix epoch time.
    Some examples:
        "Fri, 16 Aug 2019 13:40:16 +0000 (UTC)"  <-- strptime can't seem to do.
        "Thu, 29 Aug 2019 15:14:23 +0000"
        "Fri, 09 Aug 2019 13:36:08 -0700"
        "Wed, 7 Aug 2019 11:00:23 -0400"
        "Fri, 30 Aug 2019 00:22:39 +0000"
        "9 Aug 2019 22:26:43 -0400"
    """
    t = None
    s = s.strip()
    s2 = re.sub(r" \+0000 \(UTC\)$", "", s)
    if (s2 != s):
        print("'%s' -> '%s'" % (s, s2))
        s = s2

    for fmt in tformats:
        try:
            t = time.strptime(s, fmt)
            break
        except ValueError:
            pass
    if (t is None): return None
    epoch_time = time.mktime(t)
    return epoch_time

def parseArgDate(s:str) -> int:
    """Let people put in a data and optional time, in some simple but
    flexible form: yyyy-mm-dd@hh:mm:ss or any token truncation.
    @return An epoch time, or None on out-of-range field.
    TODO: Should unspecified items default to None, 0, 1, midpoint?
    TODO: timezone, fractional seconds?
    """
    s = s.strip()
    mat = re.split(r"[@+T]", s, maxsplit=1)
    if (mat.groups(2)):
        dat = mat.group(1)
        tim = mat.group(2)
    else:
        dat = mat.group(1)
        tim = None

    year = mon = mday = 0
    if (dparts):
        dparts = re.split(r"-", dat.strip())
        year = int(dparts[0])
        if len(dparts>0): mon = int(dparts[1])
        if len(dparts>1): mday = int(dparts[2])

    mat = re.match(r"(\d+)[:.](\d+)[:.](\d+)", tim.strip())
    if (mat.groups(2)):
        dat = mat.group(1)
        tim = mat.group(2)
    else:
        dat = mat.group(1)
        tim = None

    hour = minute = second = 0
    tparts = re.split(r"-", dat.strip())
    hour = int(tparts[0])
    if len(tparts>0): minute = int(tparts[1])
    if len(tparts>1): second = int(tparts[2])

    if (year<1500 or year>3000 or mon<1 or mon>12 or mday<1 or mday>31 or
        hour<0 or hour>24 or minute<0 or minute>59 or second<0 or second>59):
        return None

    ts = datetime.datetime(
        year=year, month=mon, day=mday, hour=hour, minute=minute, second=second)
    ep = ts.timestamp()
    if (args.verbose):
        print("parseArgDate gets epoch %d, ctime '%s'." % (ep, time.ctime(ep)))
    return ep


###############################################################################
# Main
#
if __name__ == "__main__":
    import argparse

    def processOptions():
        dateHelp = ("Takes truncations of yyyy-mm-ddThh:mm:ss. " +
        "Separate date vs. time with [T+@]; time parts with [:.].")
        try:
            from BlockFormatter import BlockFormatter
            parser = argparse.ArgumentParser(
                description=descr, formatter_class=BlockFormatter)
        except ImportError:
            parser = argparse.ArgumentParser(description=descr)

        parser.add_argument(
            "--content", type=str,
            help="Search for text content matching this regex.")
        parser.add_argument(
            "--extension", type=str, action="append",
            help="Include only files with this extension. Repeatable.")
        parser.add_argument(
            "--from", type=str, dest="fr",
            help="Search for From matching this regex.")
        parser.add_argument(
            "--maxtime", type=str,
            help="Search for Date <= this. " + dateHelp)
        parser.add_argument(
            "--mintime", type=str,
            help="Search for Date >= this. " + dateHelp)
        parser.add_argument(
            "--recipient", type=str, dest="recip",
            help="Search for To, Cc, or Bcc matching this regex.")
        parser.add_argument(
            "--subject", type=str,
            help="Search for Subjects matching this regex.")
        parser.add_argument(
            "--to", type=str,
            help="Search for To matching this regex.")

        parser.add_argument(
            "--iencoding", type=str, default="ASCII",
            help="Assume the (MIME) file is in this encoding.")
        parser.add_argument(
            "--ignoreCase", "-i", action="store_true",
            help="Disregard case distinctions.")
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
            "files", type=str, nargs=argparse.REMAINDER,
            help="Path(s) to input file(s)")

        args0 = parser.parse_args()
        return(args0)

    ###########################################################################
    #
    args = processOptions()
    if (not args.extension):
        args.extension = [ "emlx", "mbox", "eml" ]
    ice = r"(%s)" % ("|".join(args.extension))

    if (args.mintime):
        args.umintime = parseArgDate(args.mintime)
    if (args.maxtime):
        args.umaxtime = parseArgDate(args.maxtime)

    if (len(args.files) == 0):
        warning0("grepMail.py: No files specified....")
        doOneFile(None)
    else:
        pw = PowerWalk(args.files, open=False, close=False, includeExtensions=ice)
        pw.setOptionsFromArgparse(args)
        for path0, fh0, what0 in pw.traverse():
            if (what0 != PWType.LEAF): continue
            doOneFile(path0)
        if (not args.quiet):
            warning0("grepMail.py: Done, %d files.\n" % (pw.getStat("regular")))
