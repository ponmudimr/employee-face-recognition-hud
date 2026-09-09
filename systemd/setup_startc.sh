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

# Disable light-locker (Debian's default lightdm screen locker) so it never
# obscures the AR HUD with a lock screen. XDG per-user override
# (Hidden=true) beats the system-wide /etc/xdg/autostart entry.
mkdir -p /home/arduino/.config/autostart
cat > /home/arduino/.config/autostart/light-locker.desktop <<'EOF3'
[Desktop Entry]
Type=Application
Name=Screen Locker
Exec=light-locker
Hidden=true
EOF3
chown -R arduino:arduino /home/arduino/.config/autostart
pkill light-locker 2>/dev/null || true

echo SETUP_DONE
