#!/usr/bin/python

import glob
import os
import re
import shutil
import subprocess
import urllib
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from utils import dospath, fat32names, fixname, flatten_dir, remove_in

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
    groups: list[str] = field(default_factory=list)
    downloads: list[str] = field(default_factory=list)
    event: str = ""
    place: int = 0
    compo: str = ""
    published: str = ""
    year: int = -1
    comment: str = ""
    type: str = ""
    language: str = ""
    sids: list[str] = field(default_factory=list)

    def is_crack(self):
        return self.type.endswith("Crack")

    def is_demo(self):
        return self.type.endswith("Demo")

    def is_intro(self):
        return self.type.endswith("Intro")

    def is_music(self):
        return self.type.endswith("Music")

    def is_graphics(self):
        return self.type.endswith("Graphics")

    def is_game(self):
        return self.type.endswith("Game")

    def is_commercial(self):
        packs = [
            "Loadstar",
            "CP Verlag",
            "Binary Zone",
            " Club",
            "(Preview",
            " PD",
            "(Created",
            "Public Domain",
            "Not Publ",
            "Unknown",
        ]
        rc = not any(s in self.published for s in packs)
        return rc

    def is_typein(self):
        if self.comment.startswith("from the book"):
            return True
        return any(
            s in self.published
            for s in [
                "Commodore Info",
                "Creative Computing",
                "Infopress",
                "Hebdogiciel",
                "Markt",
                "Verlag",
                "Books",
                "Magazine",
                "Publications",
                "Press",
            ]
        )

    def format(self, template: str) -> str:
        d: dict[str, str | int | float] = {}
        for key, val in self.__dict__.items():
            if isinstance(val, str):
                d[key] = fixname(val)
            elif isinstance(val, (int, float)):
                d[key] = val
        d["groups"] = ",".join(self.groups)
        d["I"] = self.title[0].upper()
        d["A"] = fixname(self.title[0].upper())
        d["i"] = self.title[0]
        d["a"] = fixname(self.title[0])
        d["qyear"] = "XXXX" if self.year == -1 else self.year

        # Support nested curlies; if nested variable is empty or negative,
        # the outer scope is removed.
        r = re.compile(r"{[^{}]*({[^{}]+})[^{}]*}")
        while True:
            m = r.search(template)
            if not m:
                break
            s0, e0 = m.start(0), m.end(0)
            s1, e1 = m.start(1), m.end(1)
            x = template[s1:e1].format(**d)
            if x == "-1" or x == "":
                template = template[:s0] + template[e0:]
            else:
                template = template[:s0] + template[s0 + 1 : e0 - 1] + template[e0:]
        return template.format(**d)


show_output = False


def run(args: list[str | Path], cwd: Path | None = None, nostderr: bool = False) -> int:
    err = subprocess.DEVNULL if nostderr else None
    out = None if show_output else subprocess.DEVNULL
    if cwd is not None:
        return subprocess.call(args, stdout=out, stderr=err, cwd=cwd)
    return subprocess.call(args, stdout=out)


keep = {
    ".PRG",
    ".D64",
    ".T64",
    ".DIZ",
    ".NFO",
    ".TXT",
    ".REU",
    ".G64",
    ".D81",
    ".CRT",
    ".TAP",
}


def unpack(
    archive: Path,
    targetdir: Path,
    prg_to_d64: bool = False,
    d64_to_prg: bool = False,
    t64_to_prg: bool = True,
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
    remove_in(targetdir)

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
            if run(["gzip", "-d", archive]):
                # Sometimes gzip files aren't.
                os.rename(archive, archive.with_suffix(""))
            archive = archive.with_suffix("")
            ext = archive.suffix.upper()

        if ext == ".ZIP":
            # subprocess.call(["unzip", "-n", "-j", archive, "-d", targetdir])
            run(["7z", "e", archive, "-y", f"-o{targetdir}"])
        elif ext == ".RAR":
            run(["unrar", "e", "-o-", "-y", archive.absolute()], cwd=targetdir)
        elif ext == ".TAR":
            run(["tar", "-xf", archive.absolute()], cwd=targetdir)
        elif ext == ".LHA" or ext == ".LZH":
            run(["lha", "x", archive.absolute()], cwd=targetdir)
        else:
            with open(archive, "rb") as af:
                header = af.read(8)
                if header[:4] == b"PK\x03\x04" or header[:4] == b"PK\x05\x06":
                    # print("Looks like a zipfile")
                    ext = ".ZIP"
                    continue
                elif header[:4] == b"Rar!":
                    # print("Looks like a RAR file")
                    ext = ".RAR"
                    continue
                else:
                    if archive.parent != targetdir:
                        n = get_filename(archive)
                        shutil.copyfile(archive, targetdir / n)
        break

    flatten_dir(targetdir)
    # OK, `targetdir` should now contain all unpacked files

    # Convert some isoteric formats
    for r in targetdir.iterdir():
        ext = r.suffix.upper()
        if r.is_dir():
            continue
        if ext == ".GZ":
            run(["gunzip", r])
        elif r.name[:2] == "1!":
            run(["zip2disk", r.name[2:]], cwd=targetdir)
            for f in glob.glob(f"{targetdir}/?!{r.name[2:]}"):
                os.remove(f)
        elif r.suffix.upper() == ".T64" and t64_to_prg:
            tmp = targetdir / "tape"
            os.mkdir(tmp)
            run(["cbmconvert", "-t", r.absolute()], cwd=tmp, nostderr=True)
            all_basic = all(
                (x.read_bytes()[:2])[1] == 8 if x.suffix.upper() == ".PRG" else False
                for x in tmp.iterdir()
            )
            if all_basic:
                flatten_dir(targetdir)
                os.remove(r)
            else:
                # print(f"Tape {r} has non standard files, keeping...")
                remove_in(tmp)
                os.rmdir(tmp)
        elif r.suffix.upper() == ".LNX":
            n = r.with_suffix(".d64")
            run(["cbmconvert", "-D4", n.name, "-l", r.name], cwd=targetdir)
            os.remove(r)
        elif r.suffix.upper() == ".P00":
            contents = r.read_bytes()
            r.with_suffix(".prg").write_bytes(contents[0x1A:])
            os.remove(r)
        else:
            pass

    # At this point we hopfully have only PRG or D64 in our targetdir

    # Unpack D64 to PRG if requested
    if d64_to_prg:
        for r in targetdir.iterdir():
            if r.suffix.upper() == ".D64":
                run(["cbmconvert", "-N", "-d", r.name], cwd=targetdir, nostderr=True)
                # if rc != 0:
                #    print("### CBMCONVERT RETURNED %d" % (rc,))
                foundprog = False
                for r2 in targetdir.iterdir():
                    ext = r2.suffix.upper()
                    if ext == ".DEL" or ext == ".USR":
                        os.remove(r2)
                    elif ext == ".PRG":
                        foundprog = True
                if foundprog:
                    os.remove(r)

    # Put all unpacked PRG into a d64 if requested
    elif prg_to_d64:
        progs: list[str] = []
        for r in targetdir.iterdir():
            if r.suffix.upper() == ".PRG":
                progs.append(r.name)
        if progs:
            n = get_filename(archive.with_suffix(".d64"))
            print(f"Putting {progs} into {n}")
            subprocess.call(["cbmconvert", "-n", "-D4", n] + progs, cwd=targetdir)
            for p in progs:
                os.remove(targetdir / p)

    for r in targetdir.iterdir():
        ext = r.suffix.upper()
        if ext in keep:
            pass
        elif ext == ".SEQ":
            os.rename(r, r.with_suffix(".prg"))
        else:
            sz = os.path.getsize(r)
            if sz == 174848:
                os.rename(r, r.with_suffix("d64"))
            else:
                # print("Checking if %s is a PRG" % (r,))
                file = open(r, "rb")
                x = file.read(2)
                if x == b"\x01\x08":
                    os.rename(r, r.with_suffix(".prg"))
                else:
                    os.remove(r)

    fat32names(targetdir)


@contextmanager
def temp_dir() -> Generator[Path, None, None]:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as d:
        yield Path(d).resolve()


def test_unpack():
    td = Path("testdata")
    with temp_dir() as out:
        unpack(td / "with_lnx.zip", out)
        assert (out / "CHARLATA.d64").exists()
    with temp_dir() as out:
        unpack(td / "with_lnx.zip", out, d64_to_prg=True)
        assert (out / "charlatan.beyond.prg").exists()


def test_format():
    rel = Release(title="Cowboys", group="Cats", place=3)
    rel2 = Release(title="Cowboys", group="Cats", place=-1, year=1984)
    assert rel.format("{event}{{year}}") == ""
    assert rel.format("{{place:02}. }") == "03. "
    assert rel2.format("{{place:02}. }{title}{ ({year})}") == "Cowboys (1984)"
    assert rel.format("{{place:02}. }{title}{ ({year})}") == "03. Cowboys"
    assert rel.format("{{place:02}. }{title} {qyear}") == "03. Cowboys XXXX"
    t = "{event}/{compo}/{{place:02}. }{group} - {title}"
    assert rel.format(t) == "//03. Cats - Cowboys"
    assert rel2.format(t) == "//Cats - Cowboys"
