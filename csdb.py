#!/usr/bin/env python3
import argparse
from dataclasses import dataclass, field
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal
from shutil import which

from bs4 import BeautifulSoup, Tag

from tools64 import Release, unpack
from utils import fixname


@dataclass
class Link:
    id: int
    place: int = 0
    rating: float = 0
    name: str = ""


def download(url: str) -> Path | None:
    t = urllib.parse.unquote_plus(url)
    name = urllib.parse.quote_plus(t)
    file_name = Path(f"releases/{name}")
    if not file_name.exists():
        try:
            data = urllib.request.urlopen(url.replace(" ", "%20")).read()
            file_name.write_bytes(data)
        except urllib.error.HTTPError:
            return None
        except urllib.error.URLError:
            return None
    return file_name


type What = Literal["demo", "onefile", "game"]

types: dict[What, int] = {"demo": 1, "onefile": 2, "game": 3}


def get_top_list(what: What) -> str:
    if what in types.keys():
        t = types[what]
        url = rf"https://csdb.dk/toplist.php?type=release&subtype=({t})"
    else:
        raise NameError
    try:
        data: bytes = urllib.request.urlopen(url).read()
        return data.decode()
    except urllib.error.URLError as e:
        print(f"**Eror: Can not download from CSDb: {e.reason}")
        sys.exit(1)


def get_groups() -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    url = r"https://csdb.dk/toplist.php?type=group&subtype=(1)"
    data: bytes = urllib.request.urlopen(url).read()
    doc = data.decode()
    links = get_releases_from_csdb_toplist(doc)
    for link in links:
        result.append((link.name, link.id))
        print(f"{link.name} {link.id}")
    return result


def search(what: str, text: str) -> list[int]:
    text = urllib.parse.quote(text)
    url = rf"https://csdb.dk/search/?seinsel={what}&search={text}"
    data: bytes = urllib.request.urlopen(url).read()
    doc = data.decode()
    soup = BeautifulSoup(doc, "html.parser")
    ol = soup.find("ol")
    links : list[int] = []
    if isinstance(ol, Tag):
        for i,li in enumerate(ol.find_all("li")):
            href : str = li.find("a").attrs["href"]
            print(f"{i} {href}\n{li}")
            parts = href.split("=")
            links.append(int(parts[1]))
    return links



def get_releases(what: What) -> list[Link]:
    doc = get_top_list(what)
    return get_releases_from_csdb_toplist(doc)


def get_releases_from_csdb_toplist(doc: str | BeautifulSoup) -> list[Link]:
    if isinstance(doc, BeautifulSoup):
        soup = doc
    else:
        soup = BeautifulSoup(doc, "html.parser")

    # Find starting table
    b = soup.find("b", string="Place")
    table = b.find_parent("table") if b else None
    if table is None:
        sys.exit("Could not find release table")

    releases: list[Link] = []
    ok = False
    place = 0
    votes = re.compile("votes")
    for tr in table.find_all("tr"):
        if ok:
            d = tr.find_all("td")
            s = d[0].text.strip()
            if s != "":
                place = int(s)
            title = d[1].text
            href = d[1].find("a").attrs["href"]
            id = int(href.split("=")[1].strip())
            rating = float(d[2].text.strip())
            releases.append(Link(id, place, rating, title))
            # print(f"{place} {title} {id} {rating}")
        else:
            ok = tr.find("b", string=votes)
    return releases


def get_csdb_xml(what: str, id: int, depth: int = 2):
    cache = Path(f".{what}s")
    os.makedirs(cache, exist_ok=True)
    p = cache / f"{id}.xml"
    if p.exists():
        text: str = p.read_text()
    else:
        url = rf"https://csdb.dk/webservice/?type={what}&id={id}&depth={depth}"
        try:
            data: bytes = urllib.request.urlopen(url).read()
        except ValueError:
            sys.exit(f"Illegal URL: {url}")
        except (urllib.error.HTTPError, urllib.error.URLError):
            sys.exit(f"Network error for {url}")
        text: str = data.decode("utf-8")
        p.write_text(text)
    tree = ET.fromstring(text)
    return tree

def get_text(elem: ET.Element | None, default : str = "") -> str:
    if elem is not None and elem.text is not None:
        return elem.text
    return default

def get_int(elem: ET.Element | None, default : int = -1) -> int:
    if elem is not None and elem.text is not None:
        return int(elem.text)
    return default

def get_float(elem: ET.Element | None, default : float = -1) -> float:
    if elem is not None and elem.text is not None:
        return float(elem.text)
    return default

@dataclass
class Compo:
    name: str = ""
    releases: list[Link] = field(default_factory=list)

@dataclass
class Party:
    name: str = ""
    compos: list[Compo] =  field(default_factory=list)

def get_party(id:int) -> Party:
    tree = get_csdb_xml("event", id, 2)
    name = get_text(tree.find("./Event/Name"))
    party = Party(name)
    compos = tree.findall("./Event/Compo")
    for c in compos:
        type = get_text(c.find("./Type"))
        compo = Compo(type)
        for rel in c.findall("./Releases/Release"):
            place = get_int(rel.find("./Achievment/Place"))
            type = get_text(rel.find("./Type"))
            id = get_int(rel.find("./ID"))
            compo.releases.append(Link(id, place))
        party.compos.append(compo)
    return party
    

def get_group_releases(id: int) -> list[Link]:
    tree = get_csdb_xml("group", id, 2)
    rels = tree.findall("./Group/Release/Release")
    n = tree.find("./Group/Name")
    name = get_text(n, "")

    links: list[Link] = []
    print(f"{len(rels)}")
    for rel in rels:
        id_tag = rel.find("./ID")
        if id_tag is None or id_tag.text is None:
            continue
        title_tag = rel.find("./Name")
        if title_tag is None or title_tag.text is None:
            continue
        links.append(Link(int(id_tag.text), 0, 0, name))
    return links


def populate_release(link: Link) -> Release | None:
    """Use CSDb webservice to populate Release struct"""
    release = Release(link.id, link.place, link.rating, link.name)

    tree = get_csdb_xml("release", link.id)

    name = tree.find("./Release/Name")
    if name is None:
        return None
    release.title = name.text if name.text is not None else "?"
    event = tree.find(".//ReleasedAt/Event")
    if event is not None:
        release.party = get_text(event.find("./Name"))
    release.place = get_int(tree.find(".//Achievement/Place"))
    release.compo = get_text(tree.find(".//Achievement/Compo"), "No Compo")

    dls = tree.findall(".//DownloadLink")
    temp : list[tuple[int, str]] = []
    for dl in dls:
        url = get_text(dl.find("Link"))
        count = get_int(dl.find("Downloads"))
        temp.append((count, url))
    if len(temp) > 1:
        temp.sort(key = lambda t: t[0], reverse=True) 
    release.downloads = list([url for _,url in temp])
    groups = tree.findall(".//ReleasedBy/Group/Name")
    if len(groups) == 0:
        groups = tree.findall(".//ReleasedBy/Handle/Handle")

    r = tree.find("./Release/Rating")
    release.rating = get_float(r)
    y = tree.find("./Release/ReleaseYear")
    release.year = get_int(y)
    type = tree.find("./Release/Type")
    release.type = get_text(type)
    gn = [n.text for n in groups if n.text is not None]
    release.group = gn[0] if len(gn) > 0 else "Unknown"
    return release


def download_releases(releases: list[Release], template: str, to_prg: bool):
    for release in releases:
        target_dir = Path(release.format(template))
        os.makedirs(target_dir, exist_ok=True)
        # print(target_dir)
        udir = Path("_unpack")
        ok = False
        for dl in release.downloads:
            if "SourceCode" in dl:
                continue
            file = download(dl)

            if file is not None:
                if target_dir.is_dir():
                    for r in target_dir.iterdir():
                        os.remove(r)
                    os.rmdir(target_dir)
                unpack(file, udir, d64_to_prg=to_prg)
                if len(list(udir.iterdir())) > 0:
                    os.rename(udir, target_dir)
                    ok = True
                    break
        if not ok:
            print(f"Found no valid download for {release.group} - {release.title}")


class Store(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ):
        if values is None:
            return
        print(values)
        print(option_string)


def unpack_precache():
    rels = Path("data/releases.7z")
    groups = Path("data/groups.7z")
    if not os.path.exists(".releases") and rels.exists():
        print("Unpacking precached release data")
        return subprocess.call(["7z", "x", rels], stdout=subprocess.DEVNULL)
    if not os.path.exists(".groups") and groups.exists():
        print("Unpacking precached group data")
        return subprocess.call(["7z", "x", groups], stdout=subprocess.DEVNULL)


def check(tool: str, msg: str) -> bool:
    if which(tool) is None:
        print(f"**Missing** `{tool}`. {msg}")
        return False
    return True


def check_tools() -> bool:
    return (
        check("7z", "You need it to unpack (and repack) archives")
        and check("cbmconvert", "You need it to convert C64 file formats")
        and check("zip2disk", "You need it to convert C64-zip to d64")
        and check("unrar", "You need it to unpack rar files")
        and check("lha", "You need it to unpack lha and lhx files")
    )


def main():
    if not check_tools():
        return 1
    unpack_precache()


    arg_parser = argparse.ArgumentParser(
        prog="csdb_tool",
        description="Scrape CSDb",
    )

    arg_parser.add_argument(
        "-d",
        "--target-dir",
        default="Demos",
        help="Path to created directory. Used when filtering and organizing",
    )
    arg_parser.add_argument(
        "-p", "--party", nargs="*", default=None, help="Download party releases"
    )
    arg_parser.add_argument(
        "-g", "--groups", nargs="*", default=None, help="Download group releases"
    )
    arg_parser.add_argument(
        "-l", "--top-list", action='store_true', help="Download top list releases"
    )
    arg_parser.add_argument("-w", "--what", help="Download type", default="demo")
    arg_parser.add_argument(
        "-m", "--max-releases", help="Max releases to download", default=500
    )
    arg_parser.add_argument("-y", "--year-range", help="Years to download")
    arg_parser.add_argument("--to-prg", help="Convert D64 to prg", default=False)
    arg_parser.add_argument(
        "-t",
        "--directory-template",
        help="Target template",
        default="{rank:03}. {group} - {title} ({year})",
    )
    # arg_parser.add_argument(
    #     "-o",
    #     "--organize",
    #     default=True,
    #     help="Reorganize directories so each directory contains an apropriate number of files.",
    # )
    # arg_parser.add_argument(
    #     "-x", "--exclude", nargs="*", action=Store, help="Add an exclusion rule"
    # )
    # arg_parser.add_argument(
    #     "-i", "--include", nargs="*", action=Store, help="Add an inclusion rule"
    # )

    args = arg_parser.parse_args()

    if args.groups is None and args.party is None and not args.top_list:
        print("*NOTE*: You must specify what to download, groups or top-list\n")
        arg_parser.print_help()
        sys.exit(0)

    template = str(Path(args.target_dir) / args.directory_template)
    print(template)

    max_year, min_year = 99999, 1
    if args.year_range is not None:
        yr: str = args.year_range
        parts = yr.strip().split(":")
        if len(parts) == 1:
            min_year = max_year = int(parts[0])
        else:
            if parts[0] != "":
                min_year = int(parts[0])
            if parts[1] != "":
                max_year = int(parts[1])

    to_prg: bool = args.to_prg
    max_rel: int = int(args.max_releases)

    links: list[Link] = []
    print(args.party)

    parties : list[str] = args.party
    if len(parties) == 1:
        pids = search("events", parties[0])
        for pid in pids:
            party = get_party(pid)
            for compo in party.compos:
                links += compo.releases
    # if args.party:
    #     parties: list[str] = args.party
    #     for party in parties:
    #         party = get_party(int(party))
    #         for compo in party.compos:
    #             links += compo.releases
    elif args.groups:
        groups: list[str] = args.groups
        print(groups)
        if len(groups) == 0:
            get_groups()
            return
        if groups[0] == "ALL":
            print("Getting all groups")
            all = get_groups()
            all = all[:500]
            for _, id in all:
                links += get_group_releases(id)
        else:
            for group in groups:
                id = int(group)
                links += get_group_releases(id)
    else:
        what: What = args.what
        links = get_releases(what)
        print(f"Found {len(links)} releases in {what} toplist")

    print("Fetching metadata...")
    count = 0
    for link in links:
        f = Path(".releases") / f"{link.id}.xml"
        if not f.exists():
            count += 1
    print(f"Need to fetch {count} metadata")

    releases: list[Release] = []
    for link in links:
        rel = populate_release(link)
        if rel is None:
            continue
        if args.groups is not None:
            rel.group = link.name
        if rel.year < min_year or rel.year > max_year:
            continue
        # if rel.type != "C64 Demo":
        #     continue
        # if rel.rating == 0:
        #    continue
        releases.append(rel)
        if len(releases) >= max_rel:
            break
    print("Downloading releases")
    download_releases(releases, template, to_prg)


main()
