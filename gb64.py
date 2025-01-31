#!/usr/bin/env python3
from typing import Any
from pathlib import Path
import os
import sys
import argparse
from collections.abc import Callable, Sequence
import threading
import queue
from tools64 import unpack, Release
from utils import fixname, reorganize

publishers: dict[str, int] = {}


def parse_version_nfo(nfo_file: Path) -> Release:
    rel = Release()
    data = nfo_file.read_bytes().decode("iso8859_1")
    for line in data.splitlines():
        parts = line.split(":", 1)
        if len(parts) >= 2:
            key = parts[0].strip()
            val = parts[1].strip()
            if key == "Name":
                rel.title = val
            elif key == "Published":
                rel.published = val
                parts = val.split(" ", 1)
                try:
                    if len(parts) > 1:
                        name = parts[1]
                        if name in publishers:
                            publishers[name] += 1
                        else:
                            publishers[name] = 1
                    rel.year = int(parts[0])
                except ValueError:
                    pass
            elif key == "SID":
                sid = val.strip()
                if sid != "":
                    rel.sids.append(val.strip())
            elif key == "Language":
                rel.language = val.strip()
            elif key == "Genre":
                rel.type = val.strip()
            elif key == "Unique-ID":
                rel.id = int(val)
            elif key == "Comment":
                if rel.comment == "":
                    rel.comment = val
    return rel


type FC = Callable[[Release], bool]
filters: list[tuple[FC, bool]] = []

avaiable: dict[str, FC] = {
    "commercial": lambda r: r.is_commercial(),
    "type_in": lambda r: r.is_typein(),
    "have_sid": lambda r: len(r.sids) > 0,
    "year_known": lambda r: r.year > 0,
    "true": lambda r: True,
}


def add_filter(name: str, include: bool):
    invert = False
    if name.startswith("!") or name.startswith("~") or name.startswith("^"):
        invert = True
        name = name[1:]
    parts = name.split("=")
    if len(parts) > 1:
        name = parts[0]
    if name == "lang":
        fn: FC = lambda r: r.language == parts[1]  # noqa: E731
    elif name == "genre":
        fn: FC = lambda r: r.type.strip().startswith(parts[1])  # noqa: E731
    else:
        fn = avaiable[name]
    print(f"Add filter {invert} {name} as {include}")
    if invert:
        filters.append((lambda r: not fn(r), include))
    else:
        filters.append((fn, include))


def_filter: list[tuple[str, bool]] = [
    ("!commercial", False),
    ("type_in", False),
    ("!year_known", False),
    ("!lang=English", False),
    ("genre=Adventure", True),
    ("!have_sid", False),
]


def apply_filters(rel: Release) -> bool:
    for filter, val in filters:
        if filter(rel):
            return val
    return True


def filter_gb64(games: Path, target: Path, no_op: bool = False):
    for sub in games.iterdir():
        if not no_op:
            os.makedirs(target / sub.name, exist_ok=True)
        for game in sub.iterdir():
            rel = parse_version_nfo(game / "VERSION.NFO")
            keep = apply_filters(rel)
            if not keep:
                print(f"Remove {rel.title} ({rel.published})")
                if not no_op:
                    game.rename(target / game.name)


template = ""

q: queue.Queue[Callable[[], None] | None] = queue.Queue()


def worker():
    while True:
        item = q.get()
        if item is None:
            break
        item()
        q.task_done()


def convert_gb64(template: str, games: Path, no_op: bool = False):
    threads: list[threading.Thread] = []
    for _ in range(8):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    c = 0
    for zip in games.glob("**/*.zip"):
        # print(zip)
        udir = Path(f"_unpack{c}")
        c += 1
        # convert(zip, udir, template, no_op)
        q.put(lambda z=zip, u=udir: convert(z, u, template, no_op))

    for _ in threads:
        q.put(None)
    for t in threads:
        t.join()


def convert(zip: Path, udir: Path, template: str, no_op: bool):
    unpack(zip, udir)
    rel = Release()
    if len(list(udir.iterdir())) > 0:
        rel = parse_version_nfo(udir / "VERSION.NFO")
        if apply_filters(rel) and not no_op:
            target_dir = Path(rel.format(template))
            try:
                os.makedirs(target_dir)
            except FileExistsError:
                print(f"Warning: {target_dir} exists")
                target_dir = Path(str(target_dir) + f" ({rel.id})")
            os.rename(udir, target_dir)
            return
    for x in udir.iterdir():
        os.remove(x)
    os.rmdir(udir)


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
        if option_string == "-x" or option_string == "--exclude":
            add_filter(values[0], False)
        else:
            add_filter(values[0], True)
        print(values)
        print(option_string)


def main():
    # for name,val in def_filter:
    #    add_filter(name, val)

    arg_parser = argparse.ArgumentParser(
        prog="gb64_tool",
        description="Repackage GB64!",
    )

    arg_parser.add_argument("action", nargs="*", help="What to do", default=["convert"])
    arg_parser.add_argument("--check", help="Check VERSION.NFO")
    arg_parser.add_argument(
        "-G",
        "--base-dir",
        help="Path to GB64 'Games' directory. Will never be modified",
    )
    arg_parser.add_argument(
        "-T",
        "--out-dir",
        help="Path to created directory. Used when filtering and organizing",
    )
    arg_parser.add_argument(
        "-R",
        "--remove-dir",
        help="Path to remove directory. Used when filtering",
        default=Path("REMOVED"),
    )
    arg_parser.add_argument(
        "-d",
        "--destination-template",
        help="Target template",
        default="Games/{A}/{title} ({year})",
    )
    arg_parser.add_argument(
        "-o",
        "--organize",
        default=True,
        help="Reorganize directories so each directory contains an apropriate number of files.",
    )
    arg_parser.add_argument(
        "-x", "--exclude", nargs="*", action=Store, help="Add an exclusion rule"
    )
    arg_parser.add_argument(
        "-i", "--include", nargs="*", action=Store, help="Add an inclusion rule"
    )
    arg_parser.add_argument(
        "--max-files", default=250, help="Max files in one directory."
    )
    arg_parser.add_argument(
        "--min-files", default=50, help="Min files in one directory."
    )
    arg_parser.add_argument("--no-op", default=False, help="Dont actually do anything")

    args = arg_parser.parse_args()
    games = Path(args.base_dir) if args.base_dir is not None else None
    out_dir = Path(args.out_dir) if args.out_dir is not None else None
    template: str = args.destination_template
    actions: list[str] = args.action

    if args.check is not None:
        actions = []
        rel = parse_version_nfo(Path(args.check))
        keep = apply_filters(rel)
        sid = rel.sids[0] if len(rel.sids) > 0 else ""
        print(
            f"{rel.title} [{rel.published}]\n;lang:{rel.language} genre:{rel.type}\nSID:{sid}\n -> keep = {keep}"
        )

    if "convert" in actions:
        if games is None:
            sys.exit("You must specify Gamebase directory!")
        convert_gb64(template, games)
    if "filter" in actions:
        if out_dir is None:
            sys.exit("You must specify a target directory!")
        remove_dir = Path(args.remove_dir)
        filter_gb64(out_dir, remove_dir, args.no_op)
    if "organize" in actions:
        if out_dir is None:
            sys.exit("You must specify a target directory!")
        reorganize(out_dir, min_files=args.min_files, max_files=args.max_files)

    with open(".publishers", "w") as f:
        p = dict(sorted(publishers.items(), key=lambda item: item[1], reverse=True))
        for name, count in p.items():
            if count == 1:
                break
            f.write(f"{name} {count}\n")


main()
