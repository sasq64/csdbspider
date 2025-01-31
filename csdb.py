#!/usr/bin/env python3
import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from bs4 import BeautifulSoup

from tools64 import Release, unpack
from utils import fixname


def download(url: str) -> Path | None:
    t = urllib.parse.unquote_plus(url)
    name = urllib.parse.quote_plus(t)
    file_name = Path(f"releases/{name}")
    if not file_name.exists():
        try:
            data = urllib.request.urlopen(url.replace(' ', '%20')).read()
            file_name.write_bytes(data)
        except urllib.error.HTTPError: 
            return None
        except urllib.error.URLError:
            return None
    return file_name

type What = Literal["groups", "demos", "onefile"]

def get_top_list(what: What) -> str :
    if what == "groups":
        url = r"https://csdb.dk/toplist.php?type=group&subtype=(1)"
    elif what == "demos":
        url = r"https://csdb.dk/toplist.php?type=group&subtype=(1)"
    elif what == "onefile":
        url = r"https://csdb.dk/toplist.php?type=group&subtype=(1)"
    else:
        raise NameError
    data : bytes = urllib.request.urlopen(url).read()
    return data.decode()


def get_releases(what: What) -> list[Release]:
    doc = get_top_list(what)
    return get_releases_from_csdb_toplist(doc)

def get_releases_from_csdb_toplist(doc: str | BeautifulSoup):
    if isinstance(doc, BeautifulSoup):
        soup = doc
    else:
        soup = BeautifulSoup(doc, 'html.parser')

    # Find starting table
    b = soup.find("b", string="Place")
    table = b.find_parent("table") if b else None
    if table is None:
        sys.exit("Could not find release table")

    releases : list[Release] = []
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
            releases.append(Release(id, place, rating, title))
            print(f"{place} {title} {id} {rating}")
        else:
            ok = tr.find("b", string=votes)
    return releases

def populate_release(release: Release) -> bool:
    """Use CSDb webservice to populate Release struct"""

    os.makedirs("releases", exist_ok=True)
    p = Path(f"releases/{release.id}.xml")
    if p.exists():
        text : str = p.read_text()
    else:
        url = rf"https://csdb.dk/webservice/?type=release&id={release.id}&depth=2"
        try:
            data : bytes = urllib.request.urlopen(url).read()
        except ValueError:
            sys.exit(f"Illegal URL: {url}")
        except (urllib.error.HTTPError, urllib.error.URLError):
            sys.exit(f"Network error for {url}")
        text : str= data.decode("utf-8")
        p.write_text(text)
    tree = ET.fromstring(text)

    name = tree.find("./Release/Name")
    if name is None:
        return False
    release.title = name.text if name.text is not None else "?"
    dls = tree.findall(".//DownloadLink/Link")
    print(dls)
    release.downloads = list([dl.text for dl in dls if dl.text is not None])
    groups = tree.findall(".//ReleasedBy/Group/Name")
    if len(groups) == 0:
        groups = tree.findall(".//ReleasedBy/Handle/Handle")

    gn = [n.text for n in groups if n.text is not None]
    release.group = gn[0] if len(gn) > 0 else "Unknown"
    return True

def download_releases(releases: list[Release], template: str):
    for release in releases:
        if not populate_release(release):
            continue
        d : dict[str, str | int | float] = {}
        for key,val in release.__dict__.items():
            if isinstance(val,str):
                d[key] = fixname(val)
            elif isinstance(val, (int, float)):
                d[key] = val
        target_dir = Path(template.format(**d))
        os.makedirs(target_dir, exist_ok=True)
        print(target_dir)
        for dl in release.downloads:
            if "SourceCode" in dl:
                continue
            file = download(dl)

            if file is not None:
                if target_dir.is_dir():
                    for r in target_dir.iterdir():
                        os.remove(r)
                    os.rmdir(target_dir)
                udir = Path("_unpack")
                unpack(file, udir, d64_to_prg=True)
                if len(list(udir.iterdir())) > 0:
                    os.rename(udir, target_dir)
                    break

class Store(argparse.Action):
    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: str | Sequence[Any] | None, option_string: str | None = None):
        if values is None:
            return
        print(values)
        print(option_string)


def main():

    arg_parser = argparse.ArgumentParser(
        prog="csdb_tool",
        description="Scrape CSDb",
    )

    arg_parser.add_argument("-G", "--base-dir", help="Path to GB64 'Games' directory. Will never be modified")
    arg_parser.add_argument("-T", "--target-dir", help="Path to created directory. Used when filtering and organizing")
    arg_parser.add_argument("--action", nargs="*", help="What to do", default = [ "convert" ])
    arg_parser.add_argument("-d", "--destination-template",
                            help="Target template",
                            default= "Demos/{rank:3}. {group} - {title} ({year})")
    arg_parser.add_argument("-o", "--organize",
                            default = True,
                            help="Reorganize directories so each directory contains an apropriate number of files.")
    arg_parser.add_argument("-x", "--exclude", nargs="*", action=Store,
                            help="Add an exclusion rule")
    arg_parser.add_argument("-i", "--include", nargs="*", action=Store,
                            help="Add an inclusion rule")

    args = arg_parser.parse_args()
    template =args.destination_template

    releases = get_releases("demos")
    for r in releases:
        populate_release(r)
    download_releases(releases, template)

main()

