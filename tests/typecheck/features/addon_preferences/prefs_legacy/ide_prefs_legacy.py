"""What the editor shows for a legacy add-on's preferences key (check:ide; never imported).

A legacy add-on's __package__ is its folder name, so the hover can name it. An extension's is
bl_ext.<repo>.<id> with a repository the checker cannot know, so prefs_ext has no such marker.
"""

from __future__ import annotations


def package() -> None:
    __package__
    # ^hover-contains "prefs_legacy"
