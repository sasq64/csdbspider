#!/usr/bin/python

from dataclasses import dataclass, field
import os
import glob
import subprocess
import shutil
from pathlib import Path
import urllib
import urllib.parse
from utils import dospath, fat32names, fixname

is_win = False


def get_filename(url: Path) -> str:
    uq = urllib.parse.unquote_plus(url.name)
    n = fixname(Path(uq).name)
    return n

@dataclass
class Release:
    """Represent a C64 release like a Demo or a Games"""
    id: int = -1
    rank: int = 0
    rating: float = 0
    title: str = ""
    group: str = ""
    downloads: list[str] = field(default_factory=list)
    published: str = ""
    year: int = 0
    comment: str = ""
    type: str = ""
    language: str = ""
    sids: list[str] = field(default_factory=list)

    def is_commercial(self):
        packs = [ "Loadstar", "CP Verlag", "Binary Zone", "(Preview", "(Created", "Public Domain", "Not Publ", "Unknown"]
        rc = not any(s in self.published for s in packs)
        return rc

    def is_typein(self):
        return any(s in self.published for s in [ "Books", "Magazine", "Publications"])

    def format(self, template: str) -> str:
        d : dict[str, str | int | float] = {}
        for key,val in self.__dict__.items():
            if isinstance(val,str):
                d[key] = fixname(val)
            elif isinstance(val, (int, float)):
                d[key] = val
        d['I'] = self.title[0].upper()
        d['A'] = fixname(self.title[0].upper())
        d['i'] = self.title[0]
        d['a'] = fixname(self.title[0])
        return template.format(**d)


def unpack(
    archive: Path,
    targetdir: Path,
    prg_to_d64: bool = False,
    d64_to_prg: bool = False,
    t64_to_prg: bool = True,
    filter: str | None = None,
):
    """
    Generic unpack for archives containing c64 programs. Archive will be unpacked, and
    esoteric C64 formats will be converted to d64 or prg.
    .crt, .tap, .reu & .g64 will not be converted and kept.
    Info files (.txt, .nfo, .diz) will also be kept.

    `archive` - path to downloaded archive containg one C64 'release'.
    `targetdir` - Extracted/converted files will be placed here
    `to_d64` - If true, pack programs into disk images
    `to_prg` - If true, extract programs from disk images
    """

    # Make sure target directory exists and is empty
    os.makedirs(targetdir, exist_ok=True)
    res = os.listdir(targetdir)
    for r in res:
        os.remove(targetdir / r)

    if is_win:
        archive = dospath(archive)
        targetdir = dospath(targetdir)

    ext = archive.suffix.upper()

    while True:
        if ext == ".GZ":
            # Gzip replaces original file so copy it to targetdir first
            n = get_filename(archive)
            shutil.copyfile(archive, targetdir / n)
            archive = targetdir / n
            if subprocess.call(["gunzip", archive]):
                # Sometimes gzip files aren't.
                os.rename(archive, archive.with_suffix(""))
            archive = archive.with_suffix("")
            ext = archive.suffix.upper()

        if ext == ".ZIP":
            #subprocess.call(["unzip", "-n", "-j", archive, "-d", targetdir])
            subprocess.call(["7z", "e", archive, "-y", f"-o{targetdir}"], stdout=subprocess.DEVNULL)
        elif ext == ".RAR":
            subprocess.call(["unrar", "e", "-o-", "-y", archive], cwd=targetdir)
        elif ext == ".TAR":
            subprocess.call(["tar", "-xf", archive, str(targetdir) + "/"])
        elif ext == ".LHA" or ext == ".LZH":
            subprocess.call(["lha", "x", archive], cwd=targetdir)
        else:
            with open(archive, "rb") as af:
                header = af.read(8)
                if header[:4] == b"PK\x03\x04" or header[:4] == b"PK\x05\x06":
                    print("Looks like a zipfile")
                    ext = ".ZIP"
                    continue
                elif header[:4] == b"Rar!":
                    print("Looks like a RAR file")
                    ext = ".RAR"
                    continue
                else:
                    if archive.parent != targetdir:
                        n = get_filename(archive)
                        shutil.copyfile(archive, targetdir / n)
        break

    # OK, `targetdir` should now contain all unpacked files

    # Convert some isoteric formats
    res = targetdir.iterdir()
    for r in res:
        if r.name[:2] == "1!":
            subprocess.call(["zip2disk", r.name[2:]], cwd=targetdir)
            for f in glob.glob(f"{targetdir}/?!{r.name[2:]}"):
                os.remove(f)
        elif r.suffix.upper() == ".T64" and t64_to_prg:
            subprocess.call(["cbmconvert", "-t", r.name], cwd=targetdir)
            os.remove(r)
        elif r.suffix.upper() == ".LNX":
            n = r.with_suffix(".d64")
            subprocess.call(["cbmconvert", "-D4", n.name, "-l", r.name], cwd=targetdir)
            os.remove(r)
        elif r.suffix.upper() == ".P00":
            x = r.read_bytes()
            file = open(r.with_suffix(".prg"), "wb")
            file.write(x[0x1A:])
            file.close()
            os.remove(r)
        else:
            pass

    # At this point we hopfully have only PRG or D64 in our targetdir

    # Unpack D64 to PRG if requested
    if d64_to_prg:
        res = os.listdir(targetdir)
        for r in res:
            if r[-4:].upper() == ".D64":
                rc = subprocess.call(["cbmconvert", "-N", "-d", r], cwd=targetdir)
                if rc != 0:
                    print("### CBMCONVERT RETURNED %d" % (rc,))
                foundprog = False
                for r2 in os.listdir(targetdir):
                    if r2[-4:].upper() == ".DEL" or r2[-4:].upper() == ".USR":
                        os.remove(targetdir / r2)
                    elif r2[-4:].upper() == ".PRG":
                        foundprog = True
                if foundprog:
                    os.remove(targetdir / r)

    # Put all unpacked PRG into a d64 if requested
    elif prg_to_d64:
        res = os.listdir(targetdir)
        progs: list[str] = []
        for r in res:
            if r[-4:].upper() == ".PRG":
                progs.append(r)
        if progs:
            n = get_filename(archive)
            n = (
                os.path.splitext(
                    fixname(urllib.parse.unquote(os.path.basename(archive)))
                )[0]
                + ".d64"
            )
            print("Putting" + str(progs) + "into " + n)
            subprocess.call(["cbmconvert", "-n", "-D4", n] + progs, cwd=targetdir)
            for p in progs:
                os.remove(targetdir / p)

    if filter:
        res = os.listdir(targetdir)
        fsplit = filter.split()
        maxhits = 0
        bestr = None
        for r in res:
            rl = r.lower()
            rsplit = os.path.splitext(rl)
            print("Considering %s with ext %s" % (rl, rsplit[1]))
            if rsplit[1] == ".prg":
                hits = 0
                for f in fsplit:
                    if rl.find(f) >= 0:
                        hits += 1
                if hits > maxhits:
                    bestr = r
                    maxhits = hits
        if bestr:
            print("Filtered out all except " + bestr)
            for r in res:
                if r != bestr:
                    os.remove(targetdir / r)

    for r in targetdir.iterdir():
        ext = r.suffix.upper()
        if (
            ext == ".PRG"
            or ext == ".D64"
            or ext == ".T64"
            or ext == ".DIZ"
            or ext == ".NFO"
            or ext == ".TXT"
            or ext == ".REU"
            or ext == ".G64"
            or ext == ".CRT"
            or ext == ".TAP"
        ):
            pass
        elif ext == ".SEQ":
            os.rename(r, r.with_suffix(".prg"))
        else:
            sz = os.path.getsize(r)
            if sz == 174848:
                os.rename(r, r.with_suffix("d64"))
            else:
                print("Checking if %s is a PRG" % (r,))
                file = open(r, "rb")
                x = file.read(2)
                if x == b"\x01\x08":
                    os.rename(r, r.with_suffix(".prg"))
                else:
                    os.remove(r)

    fat32names(targetdir)
