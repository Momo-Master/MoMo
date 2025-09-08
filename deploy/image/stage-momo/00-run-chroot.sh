#!/bin/bash -e

# This runs inside chroot during pi-gen stage-momo

install -d /opt/momo
git clone --depth 1 https://github.com/Project-MoMo/MoMo.git /opt/momo || true
python3 -m venv /opt/momo/.venv
/opt/momo/.venv/bin/pip install --upgrade pip setuptools wheel
/opt/momo/.venv/bin/pip install -e /opt/momo

install -m 0644 /opt/momo/deploy/systemd/momo.service /etc/systemd/system/momo.service
install -m 0644 /opt/momo/deploy/firstboot/firstboot.service /etc/systemd/system/firstboot.service
systemctl enable momo.service
systemctl enable firstboot.service
touch /boot/ssh


