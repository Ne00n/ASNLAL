#!/bin/bash
set -e
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
apt-get install python3 python3-systemd python3-requests python3-pip fping git -y
cd /opt/
#git
git clone https://github.com/Ne00n/ASNLAL.git
cd ASNLAL
cp configs/asn.example.json configs/asn.json
useradd asnlal -r -d /opt/ASNLAL -s /bin/bash
chown -R asnlal:asnlal /opt/ASNLAL/
#systemd diag service
cp /opt/ASNLAL/configs/asnlal.service /etc/systemd/system/asnlal.service
systemctl enable asnlal && systemctl start asnlal