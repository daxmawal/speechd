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


def module_strip_ssml(message: str) -> str:
    nul = message.find("\0")
    if nul != -1:
        message = message[:nul]

    out = []
    append = out.append
    omit = False
    i = 0
    length = len(message)

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
        if omit:
            i += 1
            continue

        if char == "&":
            if message.startswith("&lt;", i):
                append("<")
                i += 4
                continue
            if message.startswith("&gt;", i):
                append(">")
                i += 4
                continue
            if message.startswith("&amp;", i):
                append("&")
                i += 5
                continue
            if message.startswith("&quot;", i):
                append('"')
                i += 6
                continue
            if message.startswith("&apos;", i):
                append("'")
                i += 6
                continue

        append(char)
        i += 1

    return "".join(out)
