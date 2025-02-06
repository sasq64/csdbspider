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
from typing import Any, Callable, Literal
from shutil import which

from bs4 import BeautifulSoup, Tag

from tools64 import Release, unpack
from utils import download


@dataclass
class Link:
    id: int
    place: int = 0
    rating: float = 0
    name: str = ""


type What = Literal["demo", "onefile", "game"]

types: dict[What, int] = {"demo": 1, "onefile": 2, "game": 3}


def get_soup(url: str) -> BeautifulSoup:
    try:
        data: bytes = urllib.request.urlopen(url).read()
        doc = data.decode()
        return BeautifulSoup(doc, "html.parser")
    except urllib.error.URLError as e:
        print(f"**Eror: Can not download from CSDb: {e.reason}")
        sys.exit(1)


def get_groups() -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    soup = get_soup(r"https://csdb.dk/toplist.php?type=group&subtype=(1)")
    links = get_links_from_csdb_page(soup)
    for link in links:
        result.append((link.name, link.id))
        print(f"{link.name} {link.id}")
    return result


def search(what: str, text: str) -> list[int]:
    print(text)
    text = urllib.parse.quote(text)
    print(text)
    soup = get_soup(rf"https://csdb.dk/search/?seinsel={what}&search={text}")
    return search_soup(soup)


def search_soup(soup: BeautifulSoup) -> list[int]:
    # <meta property="og:url" content="https://csdb.dk/group/?id=7" />
    meta = soup.find("meta", attrs={"property": "og:url"})
    if isinstance(meta, Tag):
        url = meta.attrs["content"]
        assert isinstance(url, str)
        parts = url.split("=")
        if len(parts) > 1 and parts[0].endswith("/?id"):
            print("Got single id in result")
            return [int(parts[1])]
    ol = soup.find("ol")
    links: list[int] = []

    if isinstance(ol, Tag):
        for i, li in enumerate(ol.find_all("li")):
            href: str = li.find("a").attrs["href"]
            #print(f"{i} {href}\n{li}")
            parts = href.split("=")
            print(parts)
            links.append(int(parts[1]))
    return links


def get_releases(what: What) -> list[Link]:
    if what in types.keys():
        t = types[what]
        url = rf"https://csdb.dk/toplist.php?type=release&subtype=({t})"
    else:
        raise NameError
    soup = get_soup(url)
    return get_links_from_csdb_page(soup)


def get_links_from_csdb_page(soup: BeautifulSoup) -> list[Link]:
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


def test_search():
    t = Path("testdata/oxyron.html").read_bytes().decode()
    soup = BeautifulSoup(t, "html.parser")
    result = search_soup(soup)
    assert len(result) == 1 and result[0] == 7
    t = Path("testdata/crackers.html").read_bytes().decode()
    soup = BeautifulSoup(t, "html.parser")
    result = search_soup(soup)
    assert len(result) > 10


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


def get_text(elem: ET.Element | None, default: str = "") -> str:
    if elem is not None and elem.text is not None:
        return elem.text
    return default


def get_int(elem: ET.Element | None, default: int = -1) -> int:
    if elem is not None and elem.text is not None:
        return int(elem.text)
    return default


def get_float(elem: ET.Element | None, default: float = -1) -> float:
    if elem is not None and elem.text is not None:
        return float(elem.text)
    return default


@dataclass
class Compo:
    name: str = ""
    releases: list[Link] = field(default_factory=list)


@dataclass
class Event:
    name: str = ""
    compos: list[Compo] = field(default_factory=list)


def get_event(id: int) -> Event:
    tree = get_csdb_xml("event", id, 2)
    name = get_text(tree.find("./Event/Name"))
    event = Event(name)
    compos = tree.findall("./Event/Compo")
    for c in compos:
        type = get_text(c.find("./Type"))
        compo = Compo(type)
        for rel in c.findall("./Releases/Release"):
            place = get_int(rel.find("./Achievment/Place"))
            type = get_text(rel.find("./Type"))
            id = get_int(rel.find("./ID"))
            compo.releases.append(Link(id, place))
        event.compos.append(compo)
    return event


def get_group_releases(id: int) -> list[Link]:
    tree = get_csdb_xml("group", id, 2)
    rels = tree.findall("./Group/Release/Release")
    n = tree.find("./Group/Name")
    name = get_text(n, "")

    links: list[Link] = []
    print(f"{name}: {len(rels)}")
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
        release.event = get_text(event.find("./Name"))
    release.place = get_int(tree.find(".//Achievement/Place"))
    release.compo = get_text(tree.find(".//Achievement/Compo"), "No Compo")

    dls = tree.findall(".//DownloadLink")
    temp: list[tuple[int, str]] = []
    for dl in dls:
        url = get_text(dl.find("Link"))
        count = get_int(dl.find("Downloads"))
        temp.append((count, url))
    if len(temp) > 1:
        temp.sort(key=lambda t: t[0], reverse=True)
    release.downloads = list([url for _, url in temp])
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


def log(txt: str):
    print(txt)


def filter_all(rel: Release):
    return True


def filter_demos(rel: Release):
    return rel.is_demo()


def filter_demos_intros(rel: Release):
    return rel.is_demo() or rel.is_intro()


def filter_non_cracks(rel: Release):
    return not rel.is_crack()


def filter_none(rel: Release):
    return False


def main():
    examples = """
# Download 10 best demos
./csdb.py -l demo -m 10

# Download Fairlight demos
./csdb.py -g Fairlight -t "Groups/{group}/{qyear} - {title} [{type}]"

# Download Gubbdata 2021 releases 
./csdb.py -e "Gubbdata 2021" -t "Parties/{event}/{compo}/{{place:02}. }{group} - {title}"
"""
    if not check_tools():
        return 1
    unpack_precache()

    arg_parser = argparse.ArgumentParser(
        prog="csdb_tool",
        description="Scrape CSDb.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    arg_parser.add_argument(
        "-e", "--event", nargs="*", default=None, help="Download event releases. Argument should either be a list of IDs, or an event name to search for."
    )
    arg_parser.add_argument(
        "-g", "--groups", nargs="*", default=None, help="Download group releases. Argument should either be a list of IDs, or a group name to search for."
    )
    arg_parser.add_argument(
        "-l",
        "--top-list",
        choices=["demo", "onefile", "game"],
        help="Download top list releases from given type.",
    )
    arg_parser.add_argument(
        "-f",
        "--filter",
        help="Types of releases to accept",
        default="non-cracks",
        choices=["all", "non-cracks", "demos", "none"],
    )
    arg_parser.add_argument(
        "-T", "--types", help="Explicit list of types to download. Matches (end of) CSDb release types.", nargs="*", default=None
    )
    arg_parser.add_argument(
        "-m", "--max-releases", help="Max releases to download", default=500
    )
    arg_parser.add_argument("-y", "--year-range", help="Limit years to download (ie 1984 or 1990:1994)")
    arg_parser.add_argument(
        "-r", "--min-rating", help="Minium rating; 0 = filter out unrated."
    )
    arg_parser.add_argument(
        "--to-prg",
        help="Convert D64 to prg",
        default=False,
    )
    arg_parser.add_argument(
        "-t",
        "--directory-template",
        help="Target template; how to save downloaded files",
        default="Demos/{rank:03}. {group} - {title}{ ({year})}",
    )

    args = arg_parser.parse_args()
    min_rating = -1

    rel_types: list[str] | None = args.types
    filter: Callable[[Release], bool] = filter_non_cracks

    if rel_types is not None:
        filter = filter_none

    if args.filter == "all":
        filter = filter_all
    elif args.filter == "demos":
        filter = filter_demos
    elif args.filter == "none":
        filter = filter_none

    if args.groups is None and args.event is None and args.top_list is None:
        print("*NOTE*: You must specify what to download; Events, groups or top-list.\nExamples:")
        print(examples)
        arg_parser.print_help()
        sys.exit(0)

    template = args.directory_template

    max_year, min_year = 99999, -1
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

    if args.event is not None:
        events: list[str] = args.event
        if len(events) > 0:
            if len(events) == 1 and not events[0].isdigit():
                pids = search("events", events[0])
                log(f"Adding {len(pids)} events")
                for pid in pids:
                    event = get_event(pid)
                    for compo in event.compos:
                        links += compo.releases
            else:
                for event in events:
                    if not event.isdigit():
                        print("*NOTE* Multiple events needs to all be integers (ids)")
                        sys.exit(0)
                    event = get_event(int(event))
                    for compo in event.compos:
                        links += compo.releases

    if args.groups is not None:
        groups: list[str] = args.groups
        print(groups)
        if len(groups) == 1 and not groups[0].isdigit():
            if groups[0] == "TOP":
                print("Getting all groups")
                all = get_groups()
                all = all[:500]
                for _, id in all:
                    links += get_group_releases(id)
            else:
                pids = search("groups", groups[0])
                for id in pids:
                    links += get_group_releases(id)
        else:
            for group in groups:
                id = int(group)
                links += get_group_releases(id)

    if args.top_list is not None:
        what: What = args.top_list
        print(f"WHAT: {what}")
        links = get_releases(what)

    print(f"Fetching {len(links)} releases")

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
        ok = False
        if rel_types is not None:
            for rt in rel_types:
                if rel.type.endswith(rt):
                    ok = True
                    break
        ok |= filter(rel)
        if not ok:
            continue
        if rel.rating < min_rating:
            continue
        releases.append(rel)
        if len(releases) >= max_rel:
            break
    print(f"Downloading {len(releases)} releases")
    download_releases(releases, template, to_prg)


if __name__ == "__main__":
    main()
