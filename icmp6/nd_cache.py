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
# icmp6/nd_cache.py - module contains class supporting ICMPv6 Neighbor Discovery cache
#


from __future__ import annotations  # Required by Python ver < 3.10

import time
from typing import Optional

import loguru

import config
import icmp6.fpa
import misc.stack as stack
from lib.ip6_address import Ip6Address
from lib.mac_address import MacAddress


class NdCache:
    """Support for ICMPv6 ND cache operations"""

    class CacheEntry:
        """Container class for cache entries"""

        def __init__(self, mac_address: MacAddress, permanent: bool = False) -> None:
            self.mac_address: MacAddress = mac_address
            self.permanent: bool = permanent
            self.creation_time: float = time.time()
            self.hit_count: int = 0

    def __init__(self) -> None:
        """Class constructor"""

        self.nd_cache: dict[Ip6Address, NdCache.CacheEntry] = {}

        if __debug__:
            self._logger = loguru.logger.bind(object_name="icmp6_nd_cache.")

        # Setup timer to execute ND Cache maintainer every second
        stack.timer.register_method(method=self._maintain_cache, delay=1000)

        if __debug__:
            self._logger.debug("Started ICMPv6 Neighbor Discovery cache")

    def _maintain_cache(self) -> None:
        """Method responsible for maintaining ND cache entries"""

        for ip6_address in list(self.nd_cache):

            # Skip permanent entries
            if self.nd_cache[ip6_address].permanent:
                continue

            # If entry age is over maximum age then discard the entry
            if time.time() - self.nd_cache[ip6_address].creation_time > config.nd_cache_entry_max_age:
                mac_address = self.nd_cache.pop(ip6_address).mac_address
                if __debug__:
                    self._logger.debug(f"Discarded expir ICMPv6 ND cache entry - {ip6_address} -> {mac_address}")

            # If entry age is close to maximum age but the entry has been used since last refresh then send out request in attempt to refresh it
            elif (
                time.time() - self.nd_cache[ip6_address].creation_time > config.nd_cache_entry_max_age - config.nd_cache_entry_refresh_time
            ) and self.nd_cache[ip6_address].hit_count:
                self.nd_cache[ip6_address].hit_count = 0
                self._send_icmp6_neighbor_solicitation(ip6_address)
                if __debug__:
                    self._logger.debug(f"Trying to refresh expiring ICMPv6 ND cache entry for {ip6_address} -> {self.nd_cache[ip6_address].mac_address}")

    def add_entry(self, ip6_address: Ip6Address, mac_address: MacAddress) -> None:
        """Add / refresh entry in cache"""

        self.nd_cache[ip6_address] = self.CacheEntry(mac_address)

    def find_entry(self, ip6_address: Ip6Address) -> Optional[MacAddress]:
        """Find entry in cache and return MAC address"""

        if nd_entry := self.nd_cache.get(ip6_address, None):
            nd_entry.hit_count += 1
            if __debug__:
                self._logger.debug(
                    f"Found {ip6_address} -> {nd_entry.mac_address} entry, age {time.time() - nd_entry.creation_time:.0f}s, hit_count {nd_entry.hit_count}"
                )
            return nd_entry.mac_address

        if __debug__:
            self._logger.debug(f"Unable to find entry for {ip6_address}, sending ICMPv6 Neighbor Solicitation message")
        self._send_icmp6_neighbor_solicitation(ip6_address)
        return None

    def _send_icmp6_neighbor_solicitation(self, icmp6_ns_target_address: Ip6Address) -> None:
        """Enqueue ICMPv6 Neighbor Solicitation packet with TX ring"""

        # Pick appropriate source address
        ip6_src = Ip6Address("::")
        for ip6_host in stack.packet_handler.ip6_host:
            if icmp6_ns_target_address in ip6_host.network:
                ip6_src = ip6_host.address

        # Send out ND Solicitation message
        stack.packet_handler._phtx_icmp6(
            ip6_src=ip6_src,
            ip6_dst=icmp6_ns_target_address.solicited_node_multicast,
            ip6_hop=255,
            icmp6_type=icmp6.ps.ICMP6_NEIGHBOR_SOLICITATION,
            icmp6_ns_target_address=icmp6_ns_target_address,
            icmp6_nd_options=[icmp6.fpa.Icmp6NdOptSLLA(stack.packet_handler.mac_unicast)],
        )