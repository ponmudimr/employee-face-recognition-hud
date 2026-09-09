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

# Real LightDM autologin so the greeter never shows at boot (separate from
# light-locker above — the greeter blocks every boot until login, not just
# after idle timeout). Idempotent: only touches the commented template
# lines, safe to re-run.
python3 - <<'EOF4'
path = "/etc/lightdm/lightdm.conf"
content = open(path).read()
content = content.replace("#autologin-user=\n", "autologin-user=arduino\n")
content = content.replace("#autologin-user-timeout=0\n", "autologin-user-timeout=0\n")
content = content.replace("#autologin-session=\n", "autologin-session=xfce\n")
open(path, "w").write(content)
EOF4

# NOTE: applying the autologin config above requires a FULL REBOOT to take
# effect. Do NOT `systemctl restart lightdm` to apply it live — that has
# been observed to knock the USB hub carrying the camera/keyboard/mouse
# offline entirely, requiring a full physical power-off (not just a warm
# reboot) to recover. See PROJECT_DOCUMENTATION.md §7.2.

echo SETUP_DONE
