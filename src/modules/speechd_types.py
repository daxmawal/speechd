
#
# speechd_types.h - types for Speech Dispatcher
#
# Copyright (C) 2001, 2002, 2003 Brailcom, o.p.s.
#
# This is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from dataclasses import dataclass


SPD_PUNCT_ALL = 0
SPD_PUNCT_NONE = 1
SPD_PUNCT_SOME = 2
SPD_PUNCT_MOST = 3

SPD_CAP_NONE = 0
SPD_CAP_SPELL = 1
SPD_CAP_ICON = 2

SPD_SPELL_OFF = 0
SPD_SPELL_ON = 1

SPD_MALE1 = 1
SPD_MALE2 = 2
SPD_MALE3 = 3
SPD_FEMALE1 = 4
SPD_FEMALE2 = 5
SPD_FEMALE3 = 6
SPD_CHILD_MALE = 7
SPD_CHILD_FEMALE = 8
SPD_UNSPECIFIED = -1

SPD_DATA_TEXT = 0
SPD_DATA_SSML = 1

SPD_IMPORTANT = 1
SPD_MESSAGE = 2
SPD_TEXT = 3
SPD_NOTIFICATION = 4
SPD_PROGRESS = 5

SPD_BEGIN = 1
SPD_END = 2
SPD_INDEX_MARKS = 4
SPD_CANCEL = 8
SPD_PAUSE = 16
SPD_RESUME = 32
SPD_ALL = 0x3F

SPD_EVENT_BEGIN = 0
SPD_EVENT_END = 1
SPD_EVENT_INDEX_MARK = 2
SPD_EVENT_CANCEL = 3
SPD_EVENT_PAUSE = 4
SPD_EVENT_RESUME = 5

SORT_BY_TIME = 0
SORT_BY_ALPHABET = 1

SPD_MSGTYPE_TEXT = 0
SPD_MSGTYPE_SOUND_ICON = 1
SPD_MSGTYPE_CHAR = 2
SPD_MSGTYPE_KEY = 3
SPD_MSGTYPE_SPELL = 99


@dataclass
class SPDVoice:
    name: str | None = None
    language: str | None = None
    variant: str | None = None


@dataclass
class SPDMsgSettings:
    rate: int = 0
    pitch: int = 0
    pitch_range: int = 0
    volume: int = 0
    punctuation_mode: int = SPD_PUNCT_NONE
    spelling_mode: int = SPD_SPELL_OFF
    cap_let_recogn: int = SPD_CAP_NONE
    voice_type: int = SPD_UNSPECIFIED
    voice: SPDVoice | None = None
