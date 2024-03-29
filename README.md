#README for FileManagement repo#

This repo contains utilities that are useful for managing files in crowded
directory subtrees, as happens a lot in corpus linguistics.

My favorite item is ''renamefiles'', which can do an awful lot of fancy
things with filenames.

''bigDirTimer'' (Python) -- test your filesystem(s) for how badly they slow down on
directories with very many files in them. Many slow down a lot.

''compareDirTrees'' -- compare the file inventories of two subtrees. This is mainly
useful if you don't have a GUI tools for this, like meld, BeyondCompare, etc.

''countExtensions'' (bash) -- Inventory the file-extensions that occur in a given subtree.

''findAncestorDirectory'' -- This looks upwards to find the nearest containing
directory that contains a given file, or is named a certain way. It's handy
for finding where an "inheritable" files lives, such as .gitconfig, .venv,
or similar.

''findDuplicateFiles'' (Python) -- Unpolished tool to search a subtree for duplicates.

''fixPermissions'' -- Check file extensions and if indicated, update the files'
"execute" permission to match. For example, if you download or mount
some .py (Python) files,
this will make them executable. No easier than using `chmod` if you only
have one such file, but very useful if you have a lot, with a mix of extensions.
It should, but does not yet, also test via the `file` command.

''flattenDirs'' -- Copy (or `--move`) all descendants of the current directory, into a
single destination directory. By default, puts the intermediate directory names
onto the front of the resulting filename (so you don't lose the information), but
with underscore instead of slash separating them. See 'splitBigDir' for a way
to at least partially undo this.

''groupFiles'' -- Move (or copy) files into new sub-folders based on common
parts of their names, such as by ignoring any final digits. It can also normalize
extensions (htm vs. html), remove unusual characters from names, etc.

''lowerExtension'' (bash) -- force the extension of a file(s) to lower case.
You can also do this with my ''renamefiles'', with a regex that uses \\L.

''lscount'' (Perl) -- Report the number of files that match.
With no arguments, reports the number of files in the current directory.

''lscruft'' (Perl) -- List files whose names suggest they are temp files, such as
being named `.bak`, `~x`, `#foo#`, `Backup 3 of X`, etc.

''lsoutline'' (Perl) -- Like `ls` but displays directory subtrees as outlines.
Can include or omit the common leading portion. Also has various options such as
including only directories, writing the output as HTML nested lists or graphviz
diagrams, etc.

''lss'' (Python) -- (unfinished `ls++`)

''lstimes'' (Python) -- Attempt to extract and display every timestamp associated
with a file. Experimental.

''macFinderInfo'' -- Attempt to show all the MacOS metadata (aka "finderInfo") for a file(s).
Gets the list of available keys from file "macOsxSpotlightKeys.xsv"

''macOsxSpotLightKeys''.xsv -- A list of the names of MacOS fiile-system metadata
items, used by `renameFiles`. These are also useful as arguments to the MacOS
`mdfind`, `mdls`, and other commands. The list is probably incomplete, but should
have most of the common ones.

''nextFilename'' (Python) -- Generate the first-available serial-number-suffixed version
of a given filename.

''renameFiles'' (Python) -- An alternative to Linux `rename`, which I think is much,
much nicer (and which works on BSD, MacOS, etc. as well). It lets you apply regex
changes to filenames, but can also do many other operations:

* Find dates, normalize their format, and/or move them to the start of names
* Add ancestor directory names to the front of filenames (see also flattenDirs, above)
* Prepend file mod/creation/access times to names
* On Mac, where downloaded file often have the source URL stored as hidden metadata.
for the file, extract that and insert it into the filename (dealing with "/", "%XX" codes, etc.)
* Recode or remove unusual characters from names.
* Resolve resulting name-conflicts by adding serial numbers of fixed width.
* Add, drop, normalize, or do various changes to file extensions.
* Convert between camel, snake, upper, lower, and bactrian case.
* Convert "Copy N of", "Copy (4)" and similar conventions to serial-numbers.
* Choose whether to affect directories, and/or "."-initial (hidden) files.
* Left-pad numbers in filenames so they're all the same width
* convert Roman numerals in filenames to decmal.

''setEmailFileTime'' (Python) -- This is intended to extract send-time from an
email file (found in the MIME header), and set that file's mod-time in the
file system to match. It's still experimental.

''splitBigDir'' (Perl) -- Split up the files in a (typically big) directory, into separate
subdirectories (which are created as needed, or can be created elsewhere). By default, files are broken into
groups based on the first character of their names. But you can group by
the first N letters (optionally ignoring non-word characters and/or doing Unicode
normalization), by file extension,
my the first match to a given regex,

''spotlite'' (Perl) -- Use MacOS "Spotlight" search to find files. The main advantages
over *nix `find` are that it's indexed (thus faster), and you can search on all
kinds of metadata that `find` may not know about. It's build on top of `mdfind`,
but hopefully much easier to use.

''watchDir'' -- Meh. Polls a specified directory and reports when it changes.

