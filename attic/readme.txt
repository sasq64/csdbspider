
CSDB SPIDER BETA1

This is a pyton tool that downloads demos from csdb

You need to have unrar, unzip, cbmconvert, zip2disk, gzip and tar in
your path for it to work properly.

The easiest way to get it to work is to use cygwin. Make sure the
unzip, gzip and tar packages are installed, and then copy the other
tools into cygwin/bin.

All webpages retreived are saved in a dir called 'urlcache' in the
current directory and reused, so the second time you download the
same releases from a group, it will not access the network and go
much quicker.

Releases are first downloaded, unpacked, converted to d64 or prg
and renamed according to metadata.


-- Sasq
