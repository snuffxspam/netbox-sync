# netbox-sync
script for synchronizing subnets and vlans

![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SNMP](https://img.shields.io/badge/SNMP-FF6600?style=for-the-badge&logo=cisco&logoColor=white)

Инструмент для синхронизации данных сетевых устройств через SNMP с NetBox

## 📌 Особенности

- Автоматическое обнаружение интерфейсов и VLAN через SNMP
- Интеграция с NetBox API
- Поддержка многопоточной обработки устройств
- Гибкая конфигурация через переменные окружения

## 🚀 Быстрый старт

### Предварительные требования
- Docker (версия 20.10.0+)
- Доступ к NetBox API
- SNMP-доступ к сетевым устройствам

### Запуск через Docker

1. Склонируйте репозиторий:
```bash
git clone https://github.com/yourusername/netbox-sync.git
cd netbox-sync
