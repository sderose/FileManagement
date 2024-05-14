#!/usr/bin/env python3
#
# checkSumDirs.py Run a checksum on a directory or tree.
# 2020-05-09: Written by Steven J. DeRose.
#
#pylint: disable= W0612
#
import sys
import os
import re
import codecs
import hashlib
from time import time, ctime  #, gmtime, localtime
import stat
import pprint
pp = pprint.PrettyPrinter(indent=4)

__metadata__ = {
    "title"        : "checkSumDirs",
    "description"  : "Run a checksum on a directory or tree.",
    "rightsHolder" : "Steven J. DeRose",
    "creator"      : "http://viaf.org/viaf/50334488",
    "type"         : "http://purl.org/dc/dcmitype/Software",
    "language"     : "Python 3.7",
    "created"      : "2020-05-09",
    "modified"     : "2020-08-08",
    "publisher"    : "http://github.com/sderose",
    "license"      : "https://creativecommons.org/licenses/by-sa/3.0/"
}
__version__ = __metadata__['modified']


descr = """
=Description=

This script will run a checksum on all files in a directory, creating a
file in the directory that has a record for each file.

Subdirectories. Well, about them.... Currently they're listed, but given a
checksum of 0. What is wanted, depends on whether you're aiming to find
parallel directories whose names and/or content may have changed, or just truly
identical directories (I'm thinking mainly of the former). So I plan to
support 3 options for what information about each subdir, to include in the
checksum of the parent:

# just the name of the subdir;

# the name of the subdir and the the names of all its
(eligible) children (in a canonical order).

# effectively, the content of the entire subtree. For the non-security-centered
purposes in mind here, it should be enough to just checksum a file such as
this script generates, if it is available for the subdirectory (thus,
dir trees should be done bottom-up).

These options are, unfortunately, not yet implemented.

==Output format==

The collected information for a directory is written to stdout as JSON, like
the sample below. You can have times written as Unix epochs (the default),
or as readable strings (specify `--ctime`).

  {
    "generator": "checkSumDirs.py",
    "time": "1589053427.475884",
    "volumeID": "...",
    "inode": "...",
    "path": "...",
    "totalFiles": 4,
    "hiddenFiles": 0,
    "backupFiles": 0,
    "symlinks": 0,
    "subdirs": 2,
    "files": [
      [    "mtime",   "size",     "ino", "filename", "dsig" ],
      [ 1589049776,       90,  22506021, "file2", "8ca06d9a8f83ea102704640bfbb0b548f1c9e7f28da1c2afe8060c1a3670082f" ],
      [ 1588900216,      160,  22506007, "0",        "a/"  ],
      [ 1589049742,       48,  22506020, "file1", "07d7e339c34f2a9d532630a5fb59a03bf14f0aadf0db4233bac59ddc20e5ffa6" ],
      [ 1588900216,       96,  22506008, "0", "b/",  ]
    ]
  }


=Related Commands=


=Known bugs and Limitations=

* When building directory digests, the script assumes they're up to date
if their mod time is more recent than that of the directory itself.
This is fairly but not entirely reliable. To override and force
them all to be rebuilt, use `--force`.

* This always uses `hashlib.sha256()`.

* The output is JSON. There is a dummy entry before the first file's info,
which has labels for the fields in the following entries. I don't see a better
way to do that in JSON: Labeling them on each instance would make the JSON
longer than XML, without gaining XML's compensating benefits
(datatyping, validation, etc).
Having no labels would be evil (see [https://xkcd.com/833/]).
JSON also lacks comments, so that's not an option either.


=To do=

* Perhaps add ls-like flag suffixes to names,
to identify links, dirs, executables, specials?

* Option to not skip backup files if a correspondingly-named original is there?

* Option to include more stat fields in the sig lines?


=History=

* 2020-05-09: Written by Steven J. DeRose.
* 2020-08-08: Add volumeID, inode, path.


=Rights=

Copyright 2020-05-09 by Steven J. DeRose. This work is licensed under a
Creative Commons Attribution-Share-alike 3.0 unported license.
See [http://creativecommons.org/licenses/by-sa/3.0/ for more information].

For the most recent version, see [http://www.derose.net/steve/utilities]
or [http://github.com/sderose>].

=Options=
"""

def warning(msg):
    sys.stderr.write(msg + "\n")


###############################################################################
#
def dirAlreadyUpToDate(path):
    """Check whether a directory has the file generated by this script, and
    has not been modified since it was build. System mod-times are not an
    absolute guarantee, but pretty reliable on the whole.
    """
    if (not os.path.isdir(path)): raise ValueError("Not a directory: " + path)

    theFile = os.path.join(path, args.outfile)
    if (not os.path.exists(theFile)): return False
    d = os.stat(path)
    dirModTime = d[stat.ST_MTIME]
    s = os.stat(theFile)
    ourModTime = s[stat.ST_MTIME]
    if (d > s): return False
    return True

def doOneDir(pathArg):
    """Make the file-sigs content for one individual directory.
    """
    path = os.path.abspath(pathArg)
    if (args.recursive):
        subdirs = [f.path for f in os.scandir(path) if f.is_dir()]
        for subdir in subdirs:
            doOneDir(subdir)

    inode = os.stat(path).st_ino
    if (not args.noVolumeID):
        volumeSerialNumber = getVolumeID(path)  # Just do this one per volume!
    else:
        volumeSerialNumber = "0"

    totalFiles = 0
    hiddenFiles = 0
    backupFiles = 0
    symlinks = 0
    subdirs = 0
    fSigs = ""
    for f in os.listdir(path):
        fpath = os.path.join(path, f)
        if (f=='.' or f=='..'): continue
        totalFiles += 1
        if (not args.hiddenFiles and f[0]=='.'):
            hiddenFiles += 1
            continue
        if (not args.backupFiles and isBackup(fpath)):
            backupFiles += 1
            continue
        if (os.path.ismount(fpath)):
            print("**** Found mount point at '%s'." % (f))
            continue
        if (not args.links and os.path.islink(fpath)):
            symlinks += 1
            continue
        if (os.path.isdir(fpath)):  # True for symlinked dirs
            f += '/'
            subdirs += 1
            dsig = get_dir_digest(path)
        else:
            dsig = get_digest(fpath)
        s = os.stat(fpath)
        # Save the name, modTime, size, iNode#
        tm = s[stat.ST_MTIME]
        if (args.ctime):
            tm = ctime(stat.ST_MTIME)
            fSigs += """    [ "%24s", %8d, %9d, "%s",%s"%s" ],\n""" % (
                tm, s[stat.ST_SIZE], s[stat.ST_INO], f,
                " " if (dsig==0) else "\n      ", dsig)
        else:
            fSigs += """    [ %10d, %8d, %9d, "%s",%s"%s", ],\n""" % (
                tm, s[stat.ST_SIZE], s[stat.ST_INO], f,
                " " if (dsig==0) else "\n      ", dsig)

    if (args.ctime):
        timeStamp = ctime()
    else:
        timeStamp = time()

    buf = """{
  "generator": "checkSumDirs.py",
  "time": "%s",
  "volumeSerialNumber": "%s",
  "inode": "%d",
  "path": "%s",
  "totalFiles": %d,
  "hiddenFiles": %d,
  "backupFiles": %d,
  "symlinks": %d,
  "subdirs": %d,
  "files": [
    [    %s"mtime",   "size",     "ino", "filename", "dsig",  ],
%s
  ]
}
""" % (timeStamp, volumeSerialNumber, inode, path,
       totalFiles, hiddenFiles, backupFiles, symlinks, subdirs,
       spaces, fSigs[0:-2])
    return(buf)

def getVolumeID(path):
    """This appears to be hard. Code here is Mac-specific.

    diskutil list -plist [deviceID] gets a big plist.

    See https://stackoverflow.com/questions/7440763
    """
    deviceID = os.stat(path).st_dev  # like 16777228

    import plistlib
    from subprocess import check_output

    resp = check_output([ 'diskutil', 'list', '-plist' ])
    warning("resp: %s" % (resp.decode(encoding="utf-8")))
    data = plistlib.loads(resp)
    diskNames = data['WholeDisks']  # ['disk0', 'disk1', 'disk2']
    warning("Disk names: %s" % (diskNames))

    allDAP = data['AllDisksAndPartitions']
    assert len(diskNames) == len(allDAP)

    theVolumeID = None
    for diskInfo in allDAP:
        devID = diskInfo['DeviceIdentifier']
        warning("Disk, devID '%s'" % (devID))
        parts = diskInfo['Partitions']
        for part in parts:
            # part should be like: {
            #   'Content': 'EFI',
            #   'DeviceIdentifier': 'disk0s1',
            #   'DiskUUID': '040FC81C-3509-42B4-B7DB-9E6F4F9348FD',
            #   'Size': 314572800,
            #   'VolumeName': 'EFI',
            #   'VolumeUUID': 'E783267B-A4C3-3556-B751-DBED770EB996'
            #   'MountPoint': '/System/Volumes/Data'  # Only if mounted
            # }
            if ('VolumeName' in part):
                warning("    VolumeUUID '%s'" % (part['VolumeUUID']))
                availableID = 'VolumeUUID'
            elif ('DiskUUID' in part):
                warning("    DiskUUID '%s'" % (part['DiskUUID']))
                availableID = 'DiskUUID'
            else:
                warning("    No VolumeName or DiskUUID in: %s" % (pp.pprint(part)))
                continue
            if ('MountPoint' in part):
                warning("        ==> MountPoint '%s'" % (part['MountPoint']))
                if (path.startswith(part['MountPoint'])):
                    warning("            MATCH: ID '%s'\nfrom:" %
                        (part[availableID]))
                    if (args.verbose): pp.pprint(part)
                    theVolumeID = part[availableID]
                    break
    return theVolumeID

def isBackup(path):
    """Examine the filename to see if this seems to be a backup file:
        foo.bak;  #foo#;  foo~;  foo.tmp;  Copy 2 of foo;  foo backup 2.txt;...
       Does not deal non-English OS localizations.
    """
    # cf original in PowerWalk.py
    keywords = r'\b(backup|copy)\b'
    if (path[0] in "~#" or path[-1] in "~#"): return True
    root, ext = os.path.splitext(path)
    if (ext in [ "bak", "bkup", "tmp" ]): return True
    if (re.match(keywords, path)): return True
    if (re.match(keywords+r'(\s\d+)?$', root)): return True
    return False

def get_dir_digest(path):
    """The only secure-ish digest would require including all the content
    (e.g. checksumming the checksums of all the contained files, recursively).
    But here we want to find directories that look largely the same to the user,
    so we will notice if one was copied even though modified.

    So we provide  few choices:
        SELF: checksum the directory file itself.
        NAMES: checksum the sorted names of the children
        APX:  checksum the name, mod date, and size of the children.
        NONE: zero.
    """
    assert os.path.isdir(path)
    if (args.dirs == "SELF"):
        return get_digest(path)
    if (args.dirs == "NAMES"):
        nameList = "\n".join(sorted(os.listdir(path)))
        return get_str_digest(nameList)
    if (args.dirs == "APX"):
        names = "\n".join(sorted(os.listdir(path)))
        return
    return 0

def get_digest(path):
    """https://stackoverflow.com/questions/22058048/hashing-a-file-in-python
    """
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            # Reading is buffered, so we can read smaller chunks.
            chunk = fh.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def get_str_digest(s):
    """Same, but just for a string.
    """
    h = hashlib.sha256()
    h.update(s)
    return h.hexdigest()


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
            "--backupFiles", action='store_true',
            help='Include any files like #f#, .bak, .tmp, Copy of f, ...')
        parser.add_argument(
            "--ctime", action='store_true', default=True,
            help='Save mod times as readable local time (default), not epoch.')
        parser.add_argument(
            "--epochtime", "--utime", dest='ctime', action='store_false',
            help='Save mod times as Unix epoch times, not ctime.')
        parser.add_argument(
            "--hiddenFiles", action='store_true',
            help='Include any hidden files.')
        parser.add_argument(
            "--links", action='store_true',
            help='Include symbolic links.')
        parser.add_argument(
            "--noVolumeID", action='store_true',
            help='Do not attempt to figure out a volume ID.')
        parser.add_argument(
            "--quiet", "-q", action='store_true',
            help='Suppress most messages.')
        parser.add_argument(
            "--recursive", action='store_true',
            help='Descend into subdirectories.')
        parser.add_argument(
            "--save", action='store_true',
            help='Save the file to disk instead of writing to stdout. See -o.')
        parser.add_argument(
            "--outfile", "-o", type=str, default=".checkSums",
            help='With --save, save to this name. Default: .checkSums.')
        parser.add_argument(
            "--unicode", action='store_const', dest='iencoding',
            const='utf8', help='Assume utf-8 for input files.')
        parser.add_argument(
            "--verbose", "-v", action='count', default=0,
            help='Add more messages (repeatable).')
        parser.add_argument(
            "--version", action='version', version=__version__,
            help='Display version information, then exit.')

        parser.add_argument(
            'files', type=str,
            nargs=argparse.REMAINDER,
            help='Path(s) to input file(s)')

        args0 = parser.parse_args()
        return(args0)


    ###########################################################################
    #
    args = processOptions()
    if (args.ctime):
        spaces = " " * 16
    else:
        spaces = ""


    if (len(args.files) == 0):
        sys.stderr.write("No dirs specified....")
        sys.exit()
    else:
        for path0 in args.files:
            if (not os.path.exists(path0)):
                print("Not found: '%s'." % (path0))
            elif (not os.path.isdir(path0)):
                print("Not a directory: '%s'." % (path0))
            else:
                info = doOneDir(path0)
                if (args.save):
                    with codecs.open(os.path.join(path0, args.outfile), 'wb',
                        encoding='utf-8') as ofh:
                        ofh.write(info)
                else:
                    print("\n"+info)

    if (not args.quiet):
        print("Done.\n")
