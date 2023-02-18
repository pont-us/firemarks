#!/usr/bin/env python3

# Copyright (c) 2022 Pontus Lurcock

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""List bookmarks on the Firefox bookmarks toolbar as org-mode links"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List
import os
import shutil
import tempfile
import configparser
import sqlite3
import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clipboard",
        "-c",
        action="store_true",
        help="write output to X clipboard, not standard output",
    )
    parser.add_argument(
        "--split",
        "-s",
        action="store_true",
        help="output separate title and URL, not org link format",
    )
    parser.add_argument(
        "--filter",
        "-f",
        action="store",
        type=str,
        help="only output bookmarks containing given text",
    )
    parser.add_argument(
        "--folder",
        "-d",
        action="store",
        type=str,
        default='toolbar',
        help="name of the bookmarks folder from which to read",
    )
    args = parser.parse_args()
    db_path = os.path.join(
        expand_path("~/.mozilla/firefox"),
        get_default_moz_profile(),
        "places.sqlite",
    )
    bookmarks = get_toolbar_bookmarks(db_path, args.folder)
    bookmarks_filtered = (
        filter(lambda b: b.contains(args.filter), bookmarks)
        if args.filter is not None
        else bookmarks
    )

    for bookmark in bookmarks_filtered:
        print(bookmark.to_org(split=args.split))
    if args.clipboard:
        subprocess.run(
            # "-loops 2" is specified because in practice (at least on my
            # system) something seems to read the clipboard as soon as it's
            # updated, so "-loops 2" is required to keep xclip running until
            # the user pastes from the clipboard.
            [
                "xclip",
                "-target",
                "UTF8_STRING",
                "-in",
                "-verbose",
                "-selection",
                "clipboard",
                "-loops",
                "2",
            ],
            check=True,
            encoding="utf-8",
            input="".join(
                map(
                    lambda b: b.to_org(split=args.split) + "\n",
                    bookmarks_filtered,
                )
            ),
        )


def get_toolbar_bookmarks(db_path: str, title: str) -> List[Bookmark]:
    with tempfile.TemporaryDirectory() as tempdir:
        db_temp_path = os.path.join(tempdir, "places.sqlite")
        # Firefox locks the database so we work from a copy
        shutil.copy2(db_path, db_temp_path)
        db = sqlite3.connect(f"file:{db_temp_path}?mode=ro", uri=True)
        cursor = db.cursor()
        cursor.execute(f"SELECT id FROM moz_bookmarks WHERE title='{title}'")
        toolbar_id = list(cursor)[0][0]
        cursor.execute(
            f"SELECT moz_places.url, moz_bookmarks.title "
            f"FROM moz_places "
            f"INNER JOIN moz_bookmarks ON moz_places.id=moz_bookmarks.fk "
            f"WHERE moz_bookmarks.parent={toolbar_id}"
        )
        return [Bookmark(url, title) for url, title in cursor]


def get_default_moz_profile():
    """Get the directory name of the default Firefox profile

    Works under Ubuntu 20.04 for standard Firefox from Ubuntu repos.
    Not guaranteed for other Firefox installs."""
    ini_path = expand_path("~/.mozilla/firefox/profiles.ini")
    config_parser = configparser.ConfigParser()
    config_parser.read(ini_path)
    for section in config_parser.sections():
        config_dict = config_parser[section]
        if "Name" in config_dict and config_dict["Name"] == "default-release":
            return config_dict["path"]
    return None


def expand_path(path):
    return os.path.expandvars(os.path.expanduser(path))


@dataclass
class Bookmark:
    url: str
    title: str

    def to_org(self, split: bool = False):
        return (
            f"* {self.title}\n  {self.url}"
            if split
            else f"- [[{self.url}][{self.title}]]"
        )

    def contains(self, text: str):
        return (
            text.lower() in self.url.lower()
            or text.lower() in self.title.lower()
        )


if __name__ == "__main__":
    main()
