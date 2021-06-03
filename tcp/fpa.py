#!/usr/bin/env python3

############################################################################
#                                                                          #
#  PyTCP - Python TCP/IP stack                                             #
#  Copyright (C) 2020-2021  Sebastian Majewski                             #
#                                                                          #
#  This program is free software: you can redistribute it and/or modify    #
#  it under the terms of the GNU General Public License as published by    #
#  the Free Software Foundation, either version 3 of the License, or       #
#  (at your option) any later version.                                     #
#                                                                          #
#  This program is distributed in the hope that it will be useful,         #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#  GNU General Public License for more details.                            #
#                                                                          #
#  You should have received a copy of the GNU General Public License       #
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                          #
#  Author's email: ccie18643@gmail.com                                     #
#  Github repository: https://github.com/ccie18643/PyTCP                   #
#                                                                          #
############################################################################


#
# tcp/fpa.py - Fast Packet Assembler support class for TCP protocol
#


from __future__ import annotations  # Required by Python ver < 3.10

import struct
from typing import Optional

import ip4.ps
import ip6.ps
import tcp.ps
from lib.tracker import Tracker
from misc.ip_helper import inet_cksum


class TcpAssembler:
    """TCP packet assembler support class"""

    ip4_proto = ip4.ps.IP4_PROTO_TCP
    ip6_next = ip6.ps.IP6_NEXT_HEADER_TCP

    def __init__(
        self,
        sport: int,
        dport: int,
        seq: int = 0,
        ack: int = 0,
        flag_ns: bool = False,
        flag_crw: bool = False,
        flag_ece: bool = False,
        flag_urg: bool = False,
        flag_ack: bool = False,
        flag_psh: bool = False,
        flag_rst: bool = False,
        flag_syn: bool = False,
        flag_fin: bool = False,
        win: int = 0,
        urp: int = 0,
        options: Optional[list[TcpOptMss | TcpOptWscale | TcpOptSackPerm | TcpOptTimestamp | TcpOptEol | TcpOptNop]] = None,
        data: Optional[bytes] = None,
        echo_tracker: Optional[Tracker] = None,
    ) -> None:
        """Class constructor"""

        self._tracker: Tracker = Tracker("TX", echo_tracker)
        self._sport: int = sport
        self._dport: int = dport
        self._seq: int = seq
        self._ack: int = ack
        self._flag_ns: bool = flag_ns
        self._flag_crw: bool = flag_crw
        self._flag_ece: bool = flag_ece
        self._flag_urg: bool = flag_urg
        self._flag_ack: bool = flag_ack
        self._flag_psh: bool = flag_psh
        self._flag_rst: bool = flag_rst
        self._flag_syn: bool = flag_syn
        self._flag_fin: bool = flag_fin
        self._win: int = win
        self._urp: int = urp
        self._options: list[TcpOptMss | TcpOptWscale | TcpOptSackPerm | TcpOptTimestamp | TcpOptEol | TcpOptNop] = [] if options is None else options
        self._data: bytes = b"" if data is None else data
        self._hlen: int = tcp.ps.TCP_HEADER_LEN + sum([len(_) for _ in self._options])

        assert self._hlen % 4 == 0, f"TCP header len {self._hlen} is not multiplcation of 4 bytes, check options... {self._options}"

    def __len__(self) -> int:
        """Length of the packet"""

        return self._hlen + len(self._data)

    def __str__(self) -> str:
        """Packet log string"""

        log = (
            f"TCP {self._sport} > {self._dport}, {'N' if self._flag_ns else ''}{'C' if self._flag_crw else ''}"
            + f"{'E' if self._flag_ece else ''}{'U' if self._flag_urg else ''}{'A' if self._flag_ack else ''}"
            + f"{'P' if self._flag_psh else ''}{'R' if self._flag_rst else ''}{'S' if self._flag_syn else ''}"
            + f"{'F' if self._flag_fin else ''}, seq {self._seq}, ack {self._ack}, win {self._win}, dlen {len(self._data)}"
        )

        for option in self._options:
            log += ", " + str(option)

        return log

    @property
    def tracker(self) -> Tracker:
        """Getter for _tracker"""

        return self._tracker

    @property
    def _raw_options(self) -> bytes:
        """Packet options in raw format"""

        raw_options = b""

        for option in self._options:
            raw_options += option.raw_option

        return raw_options

    def assemble(self, frame: memoryview, pshdr_sum: int) -> None:
        """Assemble packet into the raw form"""

        struct.pack_into(
            f"! HH L L BBH HH {len(self._raw_options)}s {len(self._data)}s",
            frame,
            0,
            self._sport,
            self._dport,
            self._seq,
            self._ack,
            self._hlen << 2 | self._flag_ns,
            self._flag_crw << 7
            | self._flag_ece << 6
            | self._flag_urg << 5
            | self._flag_ack << 4
            | self._flag_psh << 3
            | self._flag_rst << 2
            | self._flag_syn << 1
            | self._flag_fin,
            self._win,
            0,
            self._urp,
            self._raw_options,
            self._data,
        )

        struct.pack_into("! H", frame, 16, inet_cksum(frame, pshdr_sum))


#
# TCP options
#


class TcpOptEol:
    """TCP option - End of Option List (0)"""

    def __str__(self) -> str:
        """Option log string"""

        return "eol"

    def __len__(self) -> int:
        """Option length"""

        return tcp.ps.TCP_OPT_EOL_LEN

    @property
    def raw_option(self) -> bytes:
        return struct.pack("!B", tcp.ps.TCP_OPT_EOL)


class TcpOptNop:
    """TCP option - No Operation (1)"""

    def __str__(self) -> str:
        """Option log string"""

        return "nop"

    def __len__(self) -> int:
        """Option length"""

        return tcp.ps.TCP_OPT_NOP_LEN

    @property
    def raw_option(self) -> bytes:
        return struct.pack("!B", tcp.ps.TCP_OPT_NOP)


class TcpOptMss:
    """TCP option - Maximum Segment Size (2)"""

    def __init__(self, mss: int) -> None:
        self._mss = mss

    def __str__(self) -> str:
        """Option log string"""

        return f"mss {self._mss}"

    def __len__(self) -> int:
        """Option length"""

        return tcp.ps.TCP_OPT_MSS_LEN

    @property
    def raw_option(self) -> bytes:
        return struct.pack("! BB H", tcp.ps.TCP_OPT_MSS, tcp.ps.TCP_OPT_MSS_LEN, self._mss)


class TcpOptWscale:
    """TCP option - Window Scale (3)"""

    def __init__(self, wscale: int) -> None:
        self._wscale = wscale

    def __str__(self) -> str:
        """Option log string"""

        return f"wscale {self._wscale}"

    def __len__(self) -> int:
        """Option length"""

        return tcp.ps.TCP_OPT_WSCALE_LEN

    @property
    def raw_option(self) -> bytes:
        return struct.pack("! BB B", tcp.ps.TCP_OPT_WSCALE, tcp.ps.TCP_OPT_WSCALE_LEN, self._wscale)


class TcpOptSackPerm:
    """TCP option - Sack Permit (4)"""

    def __str__(self) -> str:
        """Option log string"""

        return "sack_perm"

    def __len__(self) -> int:
        """Option length"""

        return tcp.ps.TCP_OPT_SACKPERM_LEN

    @property
    def raw_option(self) -> bytes:
        return struct.pack("! BB", tcp.ps.TCP_OPT_SACKPERM, tcp.ps.TCP_OPT_SACKPERM_LEN)


class TcpOptTimestamp:
    """TCP option - Timestamp (8)"""

    def __init__(self, tsval: int, tsecr: int) -> None:
        self._tsval = tsval
        self._tsecr = tsecr

    def __str__(self) -> str:
        """Option log string"""

        return f"ts {self._tsval}/{self._tsecr}"

    def __len__(self) -> int:
        """Option length"""

        return tcp.ps.TCP_OPT_TIMESTAMP_LEN

    @property
    def raw_option(self) -> bytes:
        return struct.pack("! BB LL", tcp.ps.TCP_OPT_TIMESTAMP, tcp.ps.TCP_OPT_TIMESTAMP_LEN, self._tsval, self._tsecr)