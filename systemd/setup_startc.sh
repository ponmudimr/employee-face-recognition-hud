#!/bin/bash
set -e

# Install the fixed systemd unit (Restart=on-failure so ESC/'q' exits stay exited)
cp /home/arduino/employee-face-recognition-hud/systemd/helmet-recognition.service /etc/systemd/system/helmet-recognition.service
systemctl daemon-reload

# Passwordless sudo scoped ONLY to controlling this one systemd unit
cat > /etc/sudoers.d/helmet-recognition <<'EOF'
arduino ALL=(root) NOPASSWD: /usr/bin/systemctl start helmet-recognition.service, /usr/bin/systemctl stop helmet-recognition.service, /usr/bin/systemctl restart helmet-recognition.service, /usr/bin/systemctl status helmet-recognition.service
EOF
chmod 0440 /etc/sudoers.d/helmet-recognition
visudo -c -f /etc/sudoers.d/helmet-recognition

# "startc" command to manually (re)start the HUD
cat > /usr/local/bin/startc <<'EOF2'
#!/bin/bash
sudo systemctl start helmet-recognition.service
EOF2
chmod +x /usr/local/bin/startc

echo SETUP_DONE
