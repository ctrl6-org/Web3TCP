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
# client/dhcp4.py - DHCPv4 client
#


from __future__ import annotations

import random
from typing import TYPE_CHECKING

import dhcp4.ps
import lib.socket as socket
from lib.ip4_address import Ip4Address
from lib.logger import log

if TYPE_CHECKING:
    from lib.mac_address import MacAddress


class Dhcp4Client:
    """Class supporting Dhc4 client operation"""

    def __init__(self, mac_address: MacAddress) -> None:
        """Class constructor"""

        self._mac_address = mac_address

    def fetch(self) -> tuple[str, str | None] | tuple[None, None]:
        """IPv4 DHCP client"""

        s = socket.socket(family=socket.AF_INET4, type=socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", 68))
        s.connect(("255.255.255.255", 67))

        dhcp_xid = random.randint(0, 0xFFFFFFFF)

        # Send DHCP Discover
        s.send(
            dhcp4.ps.Dhcp4Packet(
                dhcp_op=dhcp4.ps.DHCP4_OP_REQUEST,
                dhcp_xid=dhcp_xid,
                dhcp_ciaddr=Ip4Address("0.0.0.0"),
                dhcp_yiaddr=Ip4Address("0.0.0.0"),
                dhcp_siaddr=Ip4Address("0.0.0.0"),
                dhcp_giaddr=Ip4Address("0.0.0.0"),
                dhcp_chaddr=bytes(self._mac_address),
                dhcp_msg_type=dhcp4.ps.DHCP4_MSG_DISCOVER,
                dhcp_param_req_list=[dhcp4.ps.DHCP4_OPT_SUBNET_MASK, dhcp4.ps.DHCP4_OPT_ROUTER],
                dhcp_host_name="PyTCP",
            ).raw_packet
        )
        if __debug__:
            log("dhcp4", "Sent out DHCP Discover message")

        # Wait for DHCP Offer
        try:
            dhcp_packet_rx = dhcp4.ps.Dhcp4Packet(s.recv(timeout=5))
        except socket.ReceiveTimeout:
            if __debug__:
                log("dhcp4", "Didn't receive DHCP Offer message - timeout")
            s.close()
            return None, None

        if dhcp_packet_rx.dhcp_msg_type != dhcp4.ps.DHCP4_MSG_OFFER:
            if __debug__:
                log("dhcp4", "Didn't receive DHCP Offer message - message type error")
            s.close()
            return None, None

        dhcp_srv_id = dhcp_packet_rx.dhcp_srv_id
        dhcp_yiaddr = dhcp_packet_rx.dhcp_yiaddr
        if __debug__:
            log(
                "dhcp4",
                f"ClientUdpDhcp: Received DHCP Offer from {dhcp_packet_rx.dhcp_srv_id}"
                + f"IP: {dhcp_packet_rx.dhcp_yiaddr}, Mask: {dhcp_packet_rx.dhcp_subnet_mask}, Router: {dhcp_packet_rx.dhcp_router}"
                + f"DNS: {dhcp_packet_rx.dhcp_dns}, Domain: {dhcp_packet_rx.dhcp_domain_name}",
            )

        # Send DHCP Request
        s.send(
            dhcp4.ps.Dhcp4Packet(
                dhcp_op=dhcp4.ps.DHCP4_OP_REQUEST,
                dhcp_xid=dhcp_xid,
                dhcp_ciaddr=Ip4Address("0.0.0.0"),
                dhcp_yiaddr=Ip4Address("0.0.0.0"),
                dhcp_siaddr=Ip4Address("0.0.0.0"),
                dhcp_giaddr=Ip4Address("0.0.0.0"),
                dhcp_chaddr=bytes(self._mac_address),
                dhcp_msg_type=dhcp4.ps.DHCP4_MSG_REQUEST,
                dhcp_srv_id=dhcp_srv_id,
                dhcp_req_ip_addr=dhcp_yiaddr,
                dhcp_param_req_list=[dhcp4.ps.DHCP4_OPT_SUBNET_MASK, dhcp4.ps.DHCP4_OPT_ROUTER],
                dhcp_host_name="PyTCP",
            ).raw_packet
        )

        if __debug__:
            log("dhcp4", f"Sent out DHCP Request message to {dhcp_packet_rx.dhcp_srv_id}")

        # Wait for DHCP Ack
        try:
            dhcp_packet_rx = dhcp4.ps.Dhcp4Packet(s.recv(timeout=5))
        except socket.ReceiveTimeout:
            if __debug__:
                log("dhcp4", "Didn't receive DHCP ACK message - timeout")
            s.close()
            return None, None

        if dhcp_packet_rx.dhcp_msg_type != dhcp4.ps.DHCP4_MSG_ACK:
            if __debug__:
                log("dhcp4", "Didn't receive DHCP ACK message - message type error")
            s.close()
            return None, None

        if __debug__:
            log(
                "dhcp4",
                f"Received DHCP Offer from {dhcp_packet_rx.dhcp_srv_id}"
                + f"IP: {dhcp_packet_rx.dhcp_yiaddr}, Mask: {dhcp_packet_rx.dhcp_subnet_mask}, Router: {dhcp_packet_rx.dhcp_router}"
                + f"DNS: {dhcp_packet_rx.dhcp_dns}, Domain: {dhcp_packet_rx.dhcp_domain_name}",
            )
        s.close()

        assert dhcp_packet_rx.dhcp_subnet_mask is not None
        return (
            str(dhcp_packet_rx.dhcp_yiaddr) + str(dhcp_packet_rx.dhcp_subnet_mask),
            str(dhcp_packet_rx.dhcp_router[0]) if dhcp_packet_rx.dhcp_router is not None else None,
        )
