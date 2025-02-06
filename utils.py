#!/usr/bin/python

from dataclasses import dataclass
import os
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

nametrans = bytes.maketrans(br'\/:*"<>|', b"....'().")
nametrans = nametrans[:128] + b"CueaaaaceeeiiiAAEaAooouu_OU.$Y_faiounN''" + (b'.' * 24) + b'AAAAAAACEEEEIIIIDNOOOOOx0UUUUYdBaaaaaaaceeeeiiiidnooooo+ouuuuyDy'

def fixname(s: str, removeDots: bool = True) -> str:
    ss = s.encode('iso8859_1', 'ignore')		
    if removeDots :		
        x = bytes.translate(ss, nametrans).decode('iso8859_1')
        while x and len(x) and (x[-1] == '.' or x[-1] == ' ') :
            x = x[:-1]
    else :
            x = bytes.translate(ss, nametrans).decode('iso8859_1')
    return x


def dospath(x: Path) -> Path:
    return Path(str(x).replace('/cygdrive/c', 'c:').replace('/', '\\'))


def fat32names(dirname: Path) :
    """Rename all files in directory to simple ascii names to work on FAT"""
    for f in dirname.iterdir():
        fixed = fixname(f.name)
        if f.name != fixed :
            os.rename(f, dirname / fixed)
            f = dirname / fixed
        if f.is_dir(): 
            fat32names(f)


def reorganize(root_dir: Path, max_files: int, min_files: int = -1):

    small_dirs: list[Path] = []
    small_count = 0

    for f in sorted(root_dir.iterdir()):
        if f.is_dir():
            files = sorted(f.iterdir())
            count = len(files)
            i = 0
            print(f"Found {count} in {f}")
            if small_count > 0 and small_count + count > max_files:
                if len(small_dirs) > 1:
                    t = ""
                    for s in small_dirs:
                        t += s.name[0]
                    target = root_dir / t
                    print(f"Moving to {target}")
                    target.mkdir()
                    for d in small_dirs:
                        for f2 in d.iterdir():
                            f2.rename(target / f2.name)
                        d.rmdir()
                small_count = 0
                small_dirs = []

            if len(files) > max_files:
                while len(files) > 0:
                    target = Path(f"{f}{i}")
                    print(f"Moving to {target}")
                    target.mkdir()
                    for f2 in files[0:max_files]:
                        f2.rename(target / f2.name)
                    files = files[max_files:]
                    i += 1
                os.rmdir(f)
            elif count < min_files:
                small_dirs.append(f)
                small_count +=  count
                    
    if len(small_dirs) > 1:
        t = ""
        for s in small_dirs:
            t += s.name[0]
        target = root_dir / t
        print(f"Moving to {target}")
        target.mkdir()
        for d in small_dirs:
            for f2 in d.iterdir():
                f2.rename(target / f2.name)
            d.rmdir()

#reorganize(Path("Games"), 250, 50)

def get_cached(url: str) -> Path | None:
    t = urllib.parse.unquote_plus(url)
    name = urllib.parse.quote_plus(t)
    file_name = Path(f"releases/{name}")
    if file_name.exists():
        return file_name
    return None


def download(url: str) -> Path | None:
    t = urllib.parse.unquote_plus(url)
    name = urllib.parse.quote_plus(t)
    file_name = Path(f"releases/{name}")
    os.makedirs("releases", exist_ok=True)
    if not file_name.exists():
        try:
            print(f"Downloading {url}")
            data = urllib.request.urlopen(url.replace(' ', '%20')).read()
            file_name.write_bytes(data)
        except urllib.error.HTTPError: 
            return None
        except urllib.error.URLError:
            return None
    return file_name

def remove_in(path: Path):
    for r in path.iterdir():
        if r.is_dir():
            remove_in(r)
            os.rmdir(r)
        else:
            os.remove(r)


def flatten_dir2(path: Path, to: Path):
    for r in path.iterdir():
        if r.is_dir():
            flatten_dir2(r, to)
            os.rmdir(r)
        else:
            target = to / r.name
            if not target.exists():
                r.rename(target)
            else:
                os.remove(r)


def flatten_dir(path: Path):
    """Recursively move all files in a tree to the top level"""
    for r in path.iterdir():
        if r.is_dir():
            flatten_dir2(r, path)
            os.rmdir(r)


def test_flatten_dir():
    p = Path("flatten_me")
    p.mkdir(exist_ok=True)
    remove_in(p)

    (p / "a").mkdir()
    (p / "b").mkdir()
    (p / "c").mkdir()
    (p / "a" / "f1").write_text("one")
    (p / "b" / "f1").write_text("one-b")
    (p / "c" / "f2").write_text("two")
    os.makedirs(p / "d" / "e")
    (p / "d" / "e" / "f3").write_text("three")

    flatten_dir(p)
    assert (p / "f1").is_file()
    assert (p / "f2").is_file()
    assert (p / "f3").is_file()
    assert not (p / "d").exists()
    assert not (p / "a").exists()
    assert not (p / "b").exists()

