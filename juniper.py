#!/usr/bin/env python3
"""
Скрипт для сбора VLAN-интерфейсов и подсетей с устройства Juniper MX80 по SNMP.
Значения SNMP (IP-адрес устройства, community) заданы в коде.
После сбора данных VLAN и префиксов добавляются в NetBox с использованием библиотеки requests.
"""

import re
import ipaddress
from pysnmp.hlapi import *
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HOST = 'host_ip'
COMMUNITY = 'public'

NETBOX_URL = "http://netbox.example.com"
NETBOX_TOKEN = "TOKEN"

SITE_ID = 1

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def mask_to_prefix(netmask):
    """Конвертирует маску (например, 255.255.255.0) в префикс (например, 24)"""
    return str(ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen)

def snmp_walk(oid, target, community):
    """
    Выполняет SNMP walk по заданному OID и возвращает словарь,
    где ключ – полный OID (например, "SNMPv2-SMI::mib-2.4.20.1.3.45.89.69.161"),
    а значение – полученное значение (например, "255.255.255.240").
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
            print("Ошибка:", errorIndication)
            break
        elif errorStatus:
            print('Ошибка %s at %s' % (errorStatus.prettyPrint(),
                                        errorIndex and varBinds[int(errorIndex)-1][0] or '?'))
            break
        else:
            for varBind in varBinds:
                oid_str, value = varBind
                result[str(oid_str)] = value.prettyPrint()
    return result

def get_vlan_interfaces(target, community):
    """
    Собирает VLAN-интерфейсы по SNMP, используя ifDescr (OID 1.3.6.1.2.1.2.2.1.2).
    Интерфейсы, соответствующие формату "aeX.Y" (например, "ae0.1000"),
    считаются VLAN-интерфейсами.
    
    Возвращает:
      Список имен VLAN-интерфейсов.
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
    Собирает IP-подсети с устройства по SNMP, используя OID ipAdEntNetMask (1.3.6.1.2.1.4.20.1.3).
    Из строки-ключа (OID) извлекается IP (последние 4 числа до знака "="),
    маска конвертируется в префикс, и формируется строка в виде "ip/prefix".
    
    Возвращает:
      Список строк, например: "45.89.69.161/29"
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
    Проверяет, существует ли VLAN в NetBox по vid и site_id.
    Возвращает True, если VLAN найден, иначе False.
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

def add_vlan_to_netbox(vlan_id, name, site_id):
    """
    Добавляет VLAN в NetBox, используя requests.
    Если VLAN с заданным vlan_id (vid) уже существует – пропускает создание.
    """
    if vlan_exists_in_netbox(vlan_id, site_id):
        print(f"⚠️ VLAN {vlan_id} уже есть, пропускаем.")
        return

    payload = {
        'vid': int(vlan_id),
        'name': name,
        'site': site_id,
    }
    base_url = NETBOX_URL.rstrip('/')
    url = f"{base_url}/api/ipam/vlans/"
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False)

    if response.status_code == 201:
        print(f"✅ VLAN {vlan_id} добавлен.")
    else:
        print(f"❌ Ошибка при добавлении VLAN {vlan_id}: {response.status_code} - {response.text}")

def prefix_exists_in_netbox(prefix):
    """
    Проверяет, существует ли префикс в NetBox по его строковому значению.
    Возвращает True, если префикс найден, иначе False.
    """
    base_url = NETBOX_URL.rstrip('/')
    url = f"{base_url}/api/ipam/prefixes/?prefix={prefix}"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("count", 0) > 0
    return False

def add_prefix_to_netbox(prefix, site_id):
    """
    Добавляет префикс в NetBox, используя requests.
    Если префикс уже существует – пропускает создание.
    """
    if prefix_exists_in_netbox(prefix):
        print(f"⚠️ Префикс {prefix} уже существует, пропускаем.")
        return

    payload = {"prefix": prefix}
    if site_id:
        payload["site"] = site_id
    base_url = NETBOX_URL.rstrip('/')
    url = f"{base_url}/api/ipam/prefixes/"
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False)

    if response.status_code in [200, 201]:
        print(f"✅ Префикс {prefix} добавлен.")
    else:
        print(f"❌ Ошибка при добавлении префикса {prefix}: {response.status_code} - {response.text}")

def add_vlans_to_netbox_requests(vlan_list):
    """
    Для каждого VLAN из vlan_list (например, "ae0.1000"):
      - Из строки извлекается число после точки как vlan_id (vid).
      - Вызывается функция add_vlan_to_netbox.
    """
    for vlan in vlan_list:
        match = re.search(r'ae\d+\.(\d+)', vlan)
        if match:
            vid = int(match.group(1))
        else:
            vid = 0
        add_vlan_to_netbox(vid, vlan, SITE_ID)

def add_prefixes_to_netbox_requests(prefix_list):
    """
    Для каждого элемента из prefix_list (в формате "ip/prefix", например, "45.89.69.161/29"):
      - Вызывается функция add_prefix_to_netbox.
    """
    for prefix in prefix_list:
        add_prefix_to_netbox(prefix, SITE_ID)

def main():
    # Получаем списки VLAN и подсетей (в формате "ip/prefix")
    vlan_list = get_vlan_interfaces(HOST, COMMUNITY)
    prefix_list = get_subnets(HOST, COMMUNITY)
    
    # Вывод результатов в консоль
    print("Найденные VLAN-интерфейсы:")
    print("--------------------------")
    for vlan in vlan_list:
        print(vlan)
    
    print("\nНайденные префиксы (ip/prefix):")
    print("---------------------")
    for prefix in prefix_list:
        print(prefix)
    
    # Добавляем данные в NetBox через requests
    print("\nДобавление VLAN в NetBox:")
    add_vlans_to_netbox_requests(vlan_list)
    print("\nДобавление префиксов в NetBox:")
    add_prefixes_to_netbox_requests(prefix_list)

if __name__ == '__main__':
    main()
