#!/usr/bin/env python3
#
# grepMail.py: Search the hard way for emails.
# 2021-07-15: Written by Steven J. DeRose.
#
import sys
import os
import codecs
import re
import datetime
import time
import logging
from xml.dom import minidom
from xml.dom.minidom import Node
from xml.parsers.expat import ExpatError

from PowerWalk import PowerWalk, PWType
lg = logging.getLogger("grepMail")

def fatal(m:str):
    lg.criticllogginga(m)
    sys.exit()

__metadata__ = {
    "title"        : "grepMail",
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

==Usage==

    grepMail.py [options] [files]

For example:

    grepMail.py --subject "Meeting" --from "root@example.com"

You can search by any of --subject, --from, --to, --mindate, --maxdate,
--recipient, or --content. If you specify more than one of these, all must be
satisfied for the mail to be retrieved. However, all but --mindate and --maxdate
take regexes, so you can use "|" to get OR:

    grepMail.py --subject "Meeting" --from "(root|jsmith)@example.com"

--mindate and/or --maxdate is specified like ``yyyy-mm-ddThh:mm:ss``, but you can
omit trailing components and/or leading zeros on components:

    grepMail.py --mindate '2020-1-1'

There is not yet a separate way to specify relative dates, such as finding emails
from within the last week.

==What files are searched==

This is currently set up to search Apple Mail files, which (since OS 10.4 or so) have
one message per physical file, in a slight extension of the normal MIME format.
Attachments also seem to be kept in separate files.

I expect to add support for normal .mbox files, which pack mail end-to-end with
a blank line between, and each mail's first line beginning "From:" (content lines that
would collide with this, are prefixed by ">".

You can use all the options of `PowerWalk.py` to select what files to search, such
as filtering by file extension, looking within tar, gzip, etc. archived, etc.

The output includes the path to each selected email file.
With -v or --headers, the main header fields are also shown.

==Mail locations and formats==

* Older file is arranged like:
    ~/Library/Mail/
        PersistenceInfo.plist  -- lists "VersionDirectories", each with a key ("V5", etc.),
and says which was last used.
        V7/  -- a directory named for the 'last used' version
            this has several big directories, "MailData" plus ones named with guids.
            MailData -- mostly .plist files, seems to have rules, sync info, signatures, etc.
            Each guid dir contains folders named list your mailboxes. Probably each is for

        [guid]/[mailboxname].mbox/[]
* .mbox files (aka "Maildir"): These contain any number of emails,
separated by a blank line followed
by a line starting "From:", which starts a MIME headers, which is followed by a blank line
and then the content (which may have multiple parts of different kinds, even images,
typically encoded in base64). Since an email might very well have a blank line and a
line starting "From:" in the content, such cases are escaped, for example by putting
">" before the "From:".

* Apple Mail: Stored under ~/Library/Mail, then a folder such as "V7" or "V8" (presumably
to signal successive Mail version?), then "MailData",
a folder per account?, the "Mailbox"
With MacOSX 10.4, Apple stopped using normal ".mbox" file format
(see [http://mike.laiosa.org/2009/03/01/emlx.html]). Their format puts each mail in
a separate file, with 3 parts:
** the length as an ASCII decimal number followed by \n.
** the message (seems to be in normal MIME format)
** metadata an an Apple-style property list, technically in XML, but imho odd.
It does have a useful "flags" item, with a number you can unpack into a lot of
flags bits.


=Known bugs and Limitations

* Does not deal with content-transfer-encoding
* Does not search non-text content (images, base64, etc.
* Does not search attachments.
* Doesn't do anything special for mime multipart.
* What about lines like "=?utf-8?Q?Steve?= <sderose@me.com>"?
* Searches should be repeatable, so you can find emails that were sent to
a certain group of people, regardless of order.
* Need a notion of "or", at least for email addresses.


=To do=

* Move date/time option-handling into `argparsePP.py`.
* Open chosen files with your choice of app
* Option to reset filetimes to the mime time
* Copy main fields to extended attributes.


=Related Commands=

[https://docs.python.org/3/library/email.parser.html]


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

# MIME header fields we don't care about.
# Note: We do all lookups in lower-case in order to ignore case.
discardList = [
    #"content-type",
    "content-transfer-encoding",
    #"subject",
    #"date",
    #"message-id",
    #"from",
    "mime-version",
    #"to",
    "x-universally-unique-identifier",
    "references",
    "received",
    #"in-reply-to",
    "authentication-results",
    "x-smtp-server",
    "content-disposition",
    "x-apple-content-length",
    #"cc",
    "return-path",
    "received-spf",
    #"original-recipient",
    "dkim-signature",
    "x-mantsh",
    "x-clx-shades",
    "x-dmarc-info",
    "x-dmarc-policy",
    "content-id",
    "x-uniform-type-identifier",
    "x-proofpoint-virus-version",
    #"bcc",
    "x-icl-info",
]


###############################################################################
#
def readMimeHeader(ifh, path:str, discards=None, discardX=True) -> dict:
    if (discards is None): discards = {}

    appleContentSize = None
    if (path.endswith(".emlx")):  # Apple variant
        rec = ifh.readline()
        if (re.match(r"\d+\s*$", rec)):  # Apple mail hack
            appleContentSize = int(rec)
            lg.warning("Skipped Apple content-size line (%d).", appleContentSize)
        else:
            lg.error("Bad first record in .emlx file: '%s'.", rec)

    fields = {}
    curKey = ""
    curBuf = ""
    totRead = 0
    rec = ifh.readline()
    while (rec != ""):
        totRead += len(rec)
        if (rec.strip() == ""):
            break
        mat = re.match(r"^([-\w]+):\s*(.*)", rec)
        if (mat):
            if (curBuf and curKey and curKey not in discards and
                (not discardX or not curKey.startswith("x-"))):
                fields[curKey] = curBuf
            curKey = mat.group(1).lower()
            curBuf = mat.group(2)
        elif (re.match(r"^\s", rec)):
            curBuf += rec
        else:
            raise ValueError("unparseable line in MIME header of file '%s':\n    %s" %
                (path, rec))
        rec = ifh.readline()

    if (curBuf and curKey and curBuf not in discards):
        fields[curKey] = curBuf
    return fields

def scanContent(ifh, expr:str) -> bool:
    """Compile first, with args.ignorecase.
    TODO: Make --content repeatable for AND.
    TODO: Read the plist, or at least leave positioned to do so.
    """
    for rec in ifh.readlines():
        if (rec.startswith("<?xml version=\"1.0\"")):  # End mail, start plist
            break
        if (re.search(expr, rec)): return True
    return False

def doOneFile(path:str) -> dict:
    """Read and deal with one individual file.
    @return: The MIME fields if it matched, else None.
    """
    try:
        fh = codecs.open(path, "rb", encoding=args.iencoding)
    except IOError as e:
        lg.warning("Cannot open '%s':\n    %s", path, e)
        return 0

    fields = readMimeHeader(fh, path, discards=discardList)
    #for k, v in fields.items():
    #    print("Header field '%s' = '%s'" % (k, v))

    if (fails(args.subject, fields, "subject")):
        return None
    if (fails(args.fr, fields, "from")):
        return None
    if (fails(args.to, fields, "to")):
        return None
    if (fails(args.recipient, fields, "to") and
        fails(args.recipient, fields, "cc") and
        fails(args.recipient, fields, "bcc")):
        return None
    if (args.mintime or args.maxtime):
        mailDate = parseMimeDate(fields["date"])
        if (mailDate<args.umintime or mailDate>args.umaxtime ):
            return None

    if (args.content):
        if (not scanContent(fh, args.content)): return None

    fh.close()
    return fields

def fails(expr:str, fields:list, fieldName:str) -> bool:
    """Return True iff the user gave a constraint in expr, for the fieldName;
    and the fieldName either doesn't exist or doesn't match.
    """
    if (not expr): return False
    fieldName = fieldName.lower()
    if (fieldName not in fields): return True
    if (args.ignoreCase):
        return not re.match(fields[fieldName], expr, re.I)
    else:
        return not re.match(fields[fieldName], expr)


###############################################################################
#
# Date formats such as seen in Apple Mail .emlx files
tformats = [
    "%a, %d %b %Y %H:%M:%S %z",     # Sat, 25 Jan 2020 12:19:49 -0600
    "%a, %d %b %Y %H:%M:%S %Z",     # Sat, 25 Jan 2020 12:19:49 (UTC)
    "%a, %d %b %Y %H:%M:%S",        # Sat, 25 Jan 2020 12:19:49
    "%a %b %d %H:%M:%S %Y",         # Sun Jun 20 23:21:05 1993 (per ctime)
    "%d %b %Y %H:%M:%S %z",         # 25 Jan 2020 16:10:05 -0600
    "%d %b %Y %H:%M:%S %Z",         # 25 Jan 2020 16:10:05
]

def parseMimeDate(s:str) -> int:
    """Parse a MIME "Date" into a tm_struct, then convert to Unix epoch time.
    Some examples:
        "Fri, 16 Aug 2019 13:40:16 +0000 (UTC)"  <-- strptime can't seem to do.
        "Thu, 29 Aug 2019 15:14:23 +0000"
        "Fri, 09 Aug 2019 13:36:08 -0700"
        "Wed, 7 Aug 2019 11:00:23 -0400"
        "Fri, 30 Aug 2019 00:22:39 +0000"
        "9 Aug 2019 22:26:43 -0400"
    """
    s = re.sub(r" \+0000 \(UTC\)$", "", s.strip())
    tmStruct = None
    for fmt in tformats:
        try:
            tmStruct = time.strptime(s, fmt)
            break
        except ValueError:
            pass
    if (tmStruct is None): return None
    epoch_time = time.mktime(tmStruct)
    return epoch_time


###############################################################################
#
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
    dparts = re.split(r"-", dat.strip())
    if (dparts):
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
#
def findAppleMailFiles():
    """Find the Apple Mail folder, such as "V7" (gee, I coulda had a V8...).
    It should in turn contain "MailData" (containing plists for rules, sync, etc),
    and one guid-named dir per mail account. Where you get the name/address for those
    I don't know yet.
    """
    home = os.environ["HOME"]
    if (not os.path.isdir(home)):
        fatal("HOME/ not found: '%s'." % (home))
    mailDir = os.path.join(home, "Library/Mail")
    if (not os.path.isdir(mailDir)):
        fatal("Mail/ not found: '%s'." % (mailDir))
    pinfo = os.path.join(mailDir, "PersistenceInfo.plist")
    if (not os.path.isfile(pinfo)):
        fatal("Data version plist not found: %s." % (pinfo))
    plistData = loadApplePlist(pinfo)
    #print(repr(plistData))
    luvdn = plistData[0]["LastUsedVersionDirectoryName"]
    luvd = os.path.join(mailDir, luvdn)
    if (not os.path.isdir(luvd)):
        fatal("LastUsedVersionDirectoryName not found: %s." % (luvd))
    # Here there be guids...
    return luvd


###############################################################################
#
def innerText(self:Node, sep:str='') -> str:
    """Like usual HTML `innertext`, but a function (instead of a property), and allows
    inserting something in between all the text nodes (typically a space,
    so text of list items etc. don't join up. But putting in spaces around
    HTML inlines like i and b, is occasionally wrong.
    (from domextensions)
    """
    if (self.nodeType == Node.TEXT_NODE or
        self.nodeType == Node.CDATA_SECTION_NODE):
        return self.nodeValue
    if (self.nodeType != Node.ELEMENT_NODE):  # PI, comment
        return ""
    t = ""
    for childNode in self.childNodes:
        if (t): t += sep
        t += childNode.innerText(sep=sep)
    return t

def loadApplePlist(path:str) -> dict:
    """Parse an Apple plist file in XML form, and return an equivalent Python structure.
    See [https://en.wikipedia.org/wiki/Property_list]
    See also Python 'plistlib'.
    """
    Node.innerText = innerText
    with codecs.open(path, "rb", encoding="utf-8") as ifh:
        try:
            domDoc = minidom.parse(ifh)
        except ExpatError as e:
            fatal("Cannot parse plist file at '%s':\n    %s." % (path, e))
    pl = domDoc.getElementsByTagName("plist")
    assert len(pl)==1
    return convertNode(pl[0])

def convertNode(node:Node, depth=0):
    """Recursively process one node of the parsed plist.
    <plist><dict><key>foo</key><string>bar</string>...
    """
    if (node.nodeType != Node.ELEMENT_NODE):
        return None  # caller will discard
    if (node.nodeName == "true"):
        return True
    if (node.nodeName == "false"):
        return False
    if (node.nodeName == "string"):
        return str(node.innerText())
    if (node.nodeName == "int"):
        return int(node.innerText().strip())
    if (node.nodeName == "real"):
        return float(node.innerText().strip())
    if (node.nodeName == "array" or node.nodeName == "plist"):
        rc = []
        for dsub in node.childNodes:
            datum = convertNode(dsub, depth=depth+1)
            if datum is not None: rc.append(datum)
        return rc
    if (node.nodeName == "dict"):
        rc = {}
        lastKey = "[none]"
        for dsub in node.childNodes:
            if (dsub.nodeName == "key"):
                lastKey = dsub.innerText().strip()
                if (lastKey in rc):
                    lg.error("Key '%s' already in dict: %s", lastKey, repr(dict))
            else:
                datum = convertNode(dsub, depth=depth+1)
                if datum is not None: rc[lastKey] = datum
        return rc
    raise ValueError("Unexpected tag in plist: '%s'." % (node.nodeName))


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

        # Query/filtering args
        parser.add_argument(
            "--content", type=str,
            help="Search for text content matching this regex.")
        parser.add_argument(
            "--extension", type=str, action="append",
            help="Include only files with this extension. Repeatable.")
        parser.add_argument(
            "--fr", type=str, dest="fr",
            help="Search for From matching this regex.")
        parser.add_argument(
            "--maxtime", "--maxdate", type=str,
            help="Search for Date <= this. " + dateHelp)
        parser.add_argument(
            "--mintime", "--mindate", type=str,
            help="Search for Date >= this. " + dateHelp)
        parser.add_argument(
            "--recipient", type=str,
            help="Search for To, Cc, or Bcc matching this regex.")
        parser.add_argument(
            "--subject", type=str,
            help="Search for Subjects matching this regex.")
        parser.add_argument(
            "--to", type=str,
            help="Search for To matching this regex.")

        # Other args
        parser.add_argument(
            "--findMail", action="store_true",
            help="Try the 'standard' place for MacOS Mails.")
        parser.add_argument(
            "--headers", action="store_true",
            help="Show the main header fields for selected emails.")
        parser.add_argument(
            "--iencoding", "--input-encoding", type=str, default="ASCII",
            help="Assume the (MIME) file is in this encoding.")
        parser.add_argument(
            "--ignoreCase", "--ignore-case", "-i", action="store_true",
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

    if (not (args.content or args.extension or args.fr or args.maxtime or
        args.mintime or args.recipient or args.subject or args.to)):
        lg.warning("No filtering option(s) specified.")

    if (not args.extension):
        args.extension = [ "emlx", "mbox", "eml" ]
    extensionExpr = r"(%s)" % ("|".join(args.extension))

    if (args.mintime):
        args.umintime = parseArgDate(args.mintime)
    if (args.maxtime):
        args.umaxtime = parseArgDate(args.maxtime)

    if (args.findMail):
        mailRoot = findAppleMailFiles()
        print("Located Apple Mail dirs in '%s'." % (mailRoot))
        args.files.append(mailRoot)

    if (len(args.files) == 0):
        fatal("grepMail.py: No files specified....")

    pw = PowerWalk(args.files, open=False, close=False)
    pw.applyOptionsFromArgparse(args)
    pw.setOption("recursive", True)
    pw.setOption("excludeDir", "Attachments")
    pw.setOption("includeExtensions", extensionExpr)

    nFound = 0
    for path0, fh0, what0 in pw.traverse():
        if (what0 != PWType.LEAF): continue
        headers = doOneFile(path0)
        if (headers is None): continue
        print(path0)
        nFound += 1
        if (not args.verbose and not args.headers): continue
        for hf in [ 'from', 'to', 'subject', 'date' ]:
            hfValue = headers[hf] if hf in headers else ""
            print("    %8s:  %s" % (hf.title(), hfValue))
        print("")

    if (not args.quiet):
        lg.warning("grepMail.py: Done, %d files, %d hits.\n",
            pw.getStat("regular"), nFound)
