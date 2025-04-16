# netbox-sync

![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SNMP](https://img.shields.io/badge/SNMP-FF6600?style=for-the-badge&logo=cisco&logoColor=white)

Automated network device synchronization VLANs and subnets between SNMP devices (Juniper mx80) and NetBox.

## ✨ Key Features

- Automatic interface and VLAN discovery via SNMP
- Bi-directional synchronization with NetBox
- Multi-threaded device processing
- Customizable OID mapping
- Docker-ready deployment

## 🚀 Quick Start

### Prerequisites
- Docker 20.10.0+
- NetBox API access
- SNMP v2c access to network devices

### Docker Deployment

1. Clone the repository:
```bash
git clone https://github.com/yourusername/netbox-sync.git
cd netbox-sync
```
2. Create configuration file .env:
```ini
NETBOX_URL = "https://your-netbox.domain.com:
NETBOX_TOKEN = "your_api_token_here"
SNMP_COMMUNITY = "public"
HOST = "192.168.1.1"
```
3. Build and run container:
```bash
docker build -t netbox_sync . & docker run -d netbox_sync
```
