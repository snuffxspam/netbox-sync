#!/usr/bin/env python3
"""
A script for collecting VLAN interfaces and subnets from a Juniper MX80 device over SNMP.
The values of SNMP (device IP address, community) are set in the code.
After collecting the data, VLANs and prefixes are added to the NetBox using the requests library.
"""
from pysnmp.hlapi import *
from dotenv import load_dotenv
import re
import ipaddress
import requests
import json
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

HOST = os.getenv("HOST")
COMMUNITY = os.getenv("COMMUNITY")

NETBOX_URL = os.getenv("NETBOX_URL")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")

SITE_ID = 1

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def mask_to_prefix(netmask):
    """Converts a mask (for example, 255.255.255.0) to a prefix (for example, 24)"""
    return str(ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen)

def snmp_walk(oid, target, community):
    """
    Performs an SNMP walk on the specified ID and returns the dictionary,
    where the key is the full OID (for example, "SNMPv2-SMI::mib-2.4.20.1.3.45.89.69.161"),
    and the value is the received value (for example, "255.255.255.240").
    """
    result = {}
    for (errorIndication,
         errorStatus,
         errorIndex,
         varBinds) in nextCmd(SnmpEngine(),
                              CommunityData(community, mpModel=0),
                              UdpTransportTarget((target, 161)),
                              ContextData(),
                              ObjectType(ObjectIdentity(oid)),
                              lexicographicMode=False):
        if errorIndication:
            print("Errot:", errorIndication)
            break
        elif errorStatus:
            print('Error %s at %s' % (errorStatus.prettyPrint(),
                                        errorIndex and varBinds[int(errorIndex)-1][0] or '?'))
            break
        else:
            for varBind in varBinds:
                oid_str, value = varBind
                result[str(oid_str)] = value.prettyPrint()
    return result

def get_vlan_interfaces(target, community):
    """
    Collects VLAN interfaces over SNMP using ifDescr (OID 1.3.6.1.2).
    Interfaces conforming to the "aeX.Y" (for example, "ae0.1000"),
    they are considered VLAN interfaces.
    
    Returns:
      A list of VLAN interface names.
    """
    ifDescr_oid = '1.3.6.1.2.1.2.2.1.2'
    interfaces = snmp_walk(ifDescr_oid, target, community)
    
    vlan_pattern = re.compile(r'^ae\d+\.\d+$')
    vlan_list = []
    for oid_str, descr in interfaces.items():
        if vlan_pattern.match(descr):
            vlan_list.append(descr)
    return vlan_list

def get_subnets(target, community):
    """
    Collects IP subnets from the device via SNMP using the ipAdEntNetMask OID (1.3.6.1.2.1.4.20.1.3).
    The IP (the last 4 numbers before the "=" sign) is extracted from the key string (OID),
    the mask is converted to a prefix, and the string is formed as "ip/prefix".
    
    Returns:
      A list of strings, for example: "45.89.69.161/29"
    """
    ipNetmask_oid = '1.3.6.1.2.1.4.20.1.3'
    ip_entries = snmp_walk(ipNetmask_oid, target, community)
    
    subnet_list = []
    for oid_str in ip_entries.items():
        ip_parts = oid_str[0].split('.')[-4:]
        ip_address = '.'.join(ip_parts)
        ip_prefix = ip_address+"/"+mask_to_prefix(oid_str[1])
        subnet_list.append(str(ipaddress.ip_network(ip_prefix, strict=False)))
    return subnet_list

def vlan_exists_in_netbox(vlan_id, site_id):
    """
    Checks if a VLAN exists in the NetBox by vid and site_id.
    Returns True if the VLAN is found, otherwise False.
    """
    base_url = NETBOX_URL.rstrip('/')
    url = f"{base_url}/api/ipam/vlans/?vid={vlan_id}"
    if site_id:
        url += f"&site_id={site_id}"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("count", 0) > 0
    return False

def prefix_exists_in_netbox(prefix):
    """
    Checks if the prefix exists in the NetBox by its string value.
    Returns True if the prefix is found, otherwise False.
    """
    base_url = NETBOX_URL.rstrip('/')
    url = f"{base_url}/api/ipam/prefixes/?prefix={prefix}"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("count", 0) > 0
    return False

def add_vlan_to_netbox(vlan_list):
    """
    Adds a VLAN to the NetBox using requests.
    If a VLAN with the specified vls_id (vid) already exists, it skips creation..
    """
    for vlan in vlan_list:
        match = re.search(r'ae\d+\.(\d+)', vlan)
        if match:
            vid = int(match.group(1))
        else:
            vid = 0
        if vlan_exists_in_netbox(vid, SITE_ID):
            print(f"⚠️ VLAN {vid} already exists, skip it.")
            continue

        payload = {
            'vid': int(vid),
            'name': vlan,
            'site': SITE_ID,
        }
        base_url = NETBOX_URL.rstrip('/')
        url = f"{base_url}/api/ipam/vlans/"
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False)

        if response.status_code == 201:
            print(f"✅ VLAN {vid} added.")
        else:
            print(f"Error when adding VLAN {vid}: {response.status_code} - {response.text}")

def add_prefix_to_netbox(prefix_list):
    """
    Adds a prefix to the NetBox using requests.
    If the prefix already exists, it skips creation.
    """
    for prefix in prefix_list:
        if prefix_exists_in_netbox(prefix):
            print(f"Prefix {prefix} already exists, skip it.")
            continue

        payload = {"prefix": prefix}
        payload["site"] = SITE_ID
        base_url = NETBOX_URL.rstrip('/')
        url = f"{base_url}/api/ipam/prefixes/"
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False)

        if response.status_code in [200, 201]:
            print(f"Prefix {prefix} added.")
        else:
            print(f"Error when adding a prefix {prefix}: {response.status_code} - {response.text}")

def add_vlans_to_netbox_requests(vlan_list):
    """
    For each VLAN from vlan_list (for example, "ae0.1000"):
        - The number after the dot is extracted from the string as vls_id (vid).
        - The add_vli_to_netbox function is called.
    """
    for vlan in vlan_list:
        match = re.search(r'ae\d+\.(\d+)', vlan)
        if match:
            vid = int(match.group(1))
        else:
            vid = 0
        add_vlan_to_netbox(vid, vlan, SITE_ID)

def main():
    vlan_list = get_vlan_interfaces(HOST, COMMUNITY)
    prefix_list = get_subnets(HOST, COMMUNITY)
    
    print("\nAdding VLANs to NetBox:")
    add_vlan_to_netbox(vlan_list)
    print("\nAdding prefixes to NetBox:")
    add_prefix_to_netbox(prefix_list)

if __name__ == '__main__':
    main()
