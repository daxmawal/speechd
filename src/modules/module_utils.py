#
# module_utils.py - Module utilities
#           Functions to help writing output modules for Speech Dispatcher
# Copyright (C) 2003,2006, 2007 Brailcom, o.p.s.
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1, or (at your option) any later
# version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

"""Shared helpers for Python Speech Dispatcher output modules."""

from __future__ import annotations


def module_strip_ssml(message: str) -> str:
    out = []
    omit = False
    i = 0
    length = len(message)
    entities = (
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&amp;", "&"),
        ("&quot;", '"'),
        ("&apos;", "'"),
    )

    while i < length:
        char = message[i]
        if char == "<":
            omit = True
            i += 1
            continue
        if char == ">":
            omit = False
            i += 1
            continue

        entity = next(
            (
                (entity_text, replacement)
                for entity_text, replacement in entities
                if message.startswith(entity_text, i)
            ),
            None,
        )
        if entity is not None:
            entity_text, replacement = entity
            out.append(replacement)
            i += len(entity_text)
            continue

        if not omit:
            out.append(char)
        i += 1

    return "".join(out)
