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

log_level = 0
module_audio_pars = [None] * 10
Debug = 0
CustomDebugFile = None


def module_loop(module):
    from module_process import module_process

    return module_process(module, block=True)


def module_loglevel_set(cur_item, cur_value):
    global log_level

    if cur_item != "log_level":
        return -1

    value = cur_value.lstrip()
    if not value:
        return -1

    sign = 1
    if value[0] in "+-":
        if value[0] == "-":
            sign = -1
        value = value[1:]
        if not value:
            return -1

    if not value[0].isdigit():
        return -1

    number = 0
    for char in value:
        if not char.isdigit():
            break
        number = number * 10 + int(char)

    log_level = sign * number
    return 0


def module_audio_set(cur_item, cur_value):
    audio_parameters = {
        "audio_output_method": 0,
        "audio_oss_device": 1,
        "audio_alsa_device": 2,
        "audio_nas_server": 3,
        "audio_pulse_device": 4,
        # TODO: restore AudioPulseServer option
	    # SET_AUDIO_STR(audio_pulse_server, 4)
        "audio_pulse_min_length": 5,
        # 6 reserved for speech-dispatcher module name
    }
    idx = audio_parameters.get(cur_item)
    if idx is None:
        # Unknown parameter
        return -1

    module_audio_pars[idx] = None if cur_value == "NULL" else cur_value
    return 0


def module_debug(enable, filename):
    global CustomDebugFile, Debug

    if enable:
        try:
            new_CustomDebugFile = open(filename, "w+")
        except OSError:
            return -1

        if CustomDebugFile is not None:
            CustomDebugFile.close()
        CustomDebugFile = new_CustomDebugFile
        if Debug == 1:
            Debug = 3
        else:
            Debug = 2
    else:
        if Debug == 3:
            Debug = 1
        else:
            Debug = 0

        if CustomDebugFile is not None:
            CustomDebugFile.close()
        CustomDebugFile = None

    return 0


def module_strip_ssml(message: str) -> str:
    message = message.split("\0", 1)[0]
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

        if omit:
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
