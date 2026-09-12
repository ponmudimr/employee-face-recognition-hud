"""HUD graphic overlay rendering for AR glass display using OpenCV drawing functions."""

from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# HUD Theme Colors (BGR format, for the plain-cv2-drawn face cards/reticles)
COLOR_CYAN = (255, 255, 0)
COLOR_GREEN = (0, 255, 128)
COLOR_AMBER = (0, 165, 255)
COLOR_RED = (0, 0, 255)
COLOR_BG_DARK = (20, 20, 20)
COLOR_WHITE = (255, 255, 255)
COLOR_ORANGE = (0, 140, 255)  # industrial accent, visually distinct from person cards

# Machine side-panel palette (RGB, for PIL -- sharper typography/badges than raw
# cv2.putText, adapted from a prior wearable-HMI project's proven dashboard style).
PANEL_BLACK = (10, 10, 10)
PANEL_WHITE = (228, 234, 242)
PANEL_AMBER = (255, 190, 0)
PANEL_CYAN = (0, 210, 255)
PANEL_GREEN = (0, 240, 75)
PANEL_RED = (255, 55, 55)
PANEL_GREY = (140, 148, 160)


def _panel_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a monospace TTF for panel text, searching common Linux font paths (both
    Fedora's liberation-mono-fonts layout and Debian/Raspbian's dejavu layout, so this
    works on the dev machine and the board without needing a bundled font file)."""
    stub = "-Bold" if bold else "-Regular"
    candidates = [
        f"/usr/share/fonts/liberation-mono-fonts/LiberationMono{stub}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationMono{stub}.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSansMono{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeMono{'Bold' if bold else ''}.ttf",
        f"LiberationMono{stub}.ttf",
        f"DejaVuSansMono{'-Bold' if bold else ''}.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    return ImageFont.load_default()


F_TITLE = _panel_font(13, bold=True)
F_BADGE = _panel_font(15, bold=True)
F_KEY = _panel_font(12, bold=False)
F_VAL = _panel_font(13, bold=True)
F_SUB = _panel_font(11, bold=False)


def draw_hud_card(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    name: str,
    role: str,
    emp_id: str,
    similarity: float,
    is_known: bool = True
) -> None:
    """Draw a semi-transparent HUD card with employee metadata above/beside face bounding box.

    Args:
        frame: BGR image array to draw onto.
        bbox: Bounding box tuple `(x, y, w, h)`.
        name: Person's full name.
        role: Employee role or job title.
        emp_id: Unique employee ID.
        similarity: Cosine similarity score (0.0 to 1.0).
        is_known: Whether person is recognized in employee database.
    """
    x, y, w, h = bbox
    accent_color = COLOR_GREEN if is_known else COLOR_AMBER

    # Draw bounding box corner reticles for HUD aesthetic
    line_len = max(10, min(w, h) // 4)
    thickness = 2

    # Top-Left
    cv2.line(frame, (x, y), (x + line_len, y), accent_color, thickness)
    cv2.line(frame, (x, y), (x, y + line_len), accent_color, thickness)
    # Top-Right
    cv2.line(frame, (x + w, y), (x + w - line_len, y), accent_color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + line_len), accent_color, thickness)
    # Bottom-Left
    cv2.line(frame, (x, y + h), (x + line_len, y + h), accent_color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - line_len), accent_color, thickness)
    # Bottom-Right
    cv2.line(frame, (x + w, y + h), (x + w - line_len, y + h), accent_color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - line_len), accent_color, thickness)

    img_h, img_w = frame.shape[:2]
    scale_factor = img_w / 640.0
    
    # Scale box and font dynamically based on resolution
    base_w = int(max(180 * scale_factor, w + (40 * scale_factor)))
    card_w = base_w
    card_h = int(70 * scale_factor) if is_known else int(35 * scale_factor)
    card_x = max(5, x)
    card_y = max(5, y - card_h - int(10 * scale_factor))

    # Ensure card fits within frame bounds
    if card_y < 0:
        card_y = y + h + int(10 * scale_factor)
    if card_x + card_w > img_w:
        card_x = max(5, img_w - card_w - 5)

    # Draw semi-transparent dark background card
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (card_x, card_y),
        (card_x + card_w, card_y + card_h),
        COLOR_BG_DARK,
        -1
    )
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    cv2.rectangle(
        frame,
        (card_x, card_y),
        (card_x + card_w, card_y + card_h),
        accent_color,
        int(1 * scale_factor) or 1
    )

    # Draw text lines inside info card
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45 * scale_factor
    th = int(1 * scale_factor) or 1

    if is_known:
        cv2.putText(frame, f"NAME: {name}", (card_x + int(8*scale_factor), card_y + int(18*scale_factor)), font, font_scale, COLOR_WHITE, th)
        cv2.putText(frame, f"ROLE: {role}", (card_x + int(8*scale_factor), card_y + int(36*scale_factor)), font, font_scale, COLOR_CYAN, th)
        cv2.putText(frame, f"ID: {emp_id} | {int(similarity * 100)}%", (card_x + int(8*scale_factor), card_y + int(54*scale_factor)), font, font_scale, COLOR_GREEN, th)
    else:
        cv2.putText(frame, "UNKNOWN SUBJECT", (card_x + int(8*scale_factor), card_y + int(22*scale_factor)), font, font_scale, COLOR_AMBER, th)


def _render_panel(
    width: int,
    title: str,
    subtitle: Optional[str],
    badge: Optional[Tuple[str, Tuple[int, int, int]]],
    kv_rows: List[Tuple[str, str, Tuple[int, int, int]]],
    accent_rgb: Tuple[int, int, int]
) -> np.ndarray:
    """Render one bordered dashboard section (title + optional badge + key/value rows)
    via PIL for sharp anti-aliased text, sized to its content, returned as a BGR array
    ready to paste directly into a cv2 frame.

    Args:
        width: Panel width in pixels.
        title: Uppercase section title shown next to the accent bullet.
        subtitle: Optional dimmed line under the title (e.g. the machine's full name).
        badge: Optional `(text, color)` for a large status badge (e.g. RUNNING/STOPPED).
        kv_rows: List of `(key, value, value_color)` rows, key left / value right-aligned.
        accent_rgb: Border and bullet accent color.

    Returns:
        BGR numpy array of shape (height, width, 3) -- height fits the content exactly.
    """
    margin = 6
    title_h = 22
    badge_h = 26 if badge else 0
    row_h = 19
    pad_bottom = 8
    height = margin * 2 + title_h + (badge_h + 6 if badge else 0) + row_h * len(kv_rows) + pad_bottom
    if subtitle:
        height += 14

    img = Image.new("RGB", (width, height), PANEL_BLACK)
    d = ImageDraw.Draw(img)

    # Border + top accent bar
    d.rectangle((0, 0, width - 1, height - 1), outline=accent_rgb, width=2)
    d.rectangle((3, 3, width - 4, 6), fill=accent_rgb)

    # Title: bullet + uppercase text, then thin separator
    tx, ty = margin + 4, margin + 8
    d.ellipse((tx, ty + 2, tx + 6, ty + 8), fill=accent_rgb)
    d.text((tx + 11, ty - 2), title.upper(), fill=accent_rgb, font=F_TITLE)
    y = margin + title_h
    if subtitle:
        d.text((margin + 4, y), subtitle, fill=PANEL_GREY, font=F_SUB)
        y += 14
    d.line((margin, y, width - margin, y), fill=accent_rgb, width=1)
    y += 6

    if badge:
        text, color = badge
        x0, x1 = margin + 2, width - margin - 2
        d.rectangle((x0, y, x1, y + badge_h), outline=color, width=2)
        d.text((x0 + 8, y + 5), text, fill=color, font=F_BADGE)
        y += badge_h + 6

    for key, val, val_color in kv_rows:
        d.text((margin + 4, y), key, fill=PANEL_GREY, font=F_KEY)
        bbox = d.textbbox((0, 0), val, font=F_VAL)
        val_w = bbox[2] - bbox[0]
        d.text((width - margin - 4 - val_w, y - 1), val, fill=val_color, font=F_VAL)
        y += row_h

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def draw_side_panel(
    frame: np.ndarray,
    title: str,
    side: str,
    accent_rgb: Tuple[int, int, int],
    subtitle: Optional[str] = None,
    badge: Optional[Tuple[str, Tuple[int, int, int]]] = None,
    kv_rows: Optional[List[Tuple[str, str, Tuple[int, int, int]]]] = None,
    top_offset_frac: float = 0.10
) -> None:
    """Paste a rendered dashboard section onto the left or right edge of the frame, so
    the center stays clear for the camera view (a fixed sci-fi-HUD layout rather than a
    card that follows the tracked object around and can obscure it).

    Args:
        frame: BGR image array to draw onto (modified in place).
        title: Section title (see `_render_panel`).
        side: `"left"` or `"right"` -- which edge to anchor to.
        accent_rgb: Border/accent color (RGB, since this goes through PIL).
        subtitle, badge, kv_rows: See `_render_panel`.
        top_offset_frac: Vertical start position as a fraction of frame height.
    """
    img_h, img_w = frame.shape[:2]
    scale_factor = img_w / 640.0
    panel_w = int(200 * scale_factor)

    panel_bgr = _render_panel(panel_w, title, subtitle, badge, kv_rows or [], accent_rgb)
    panel_h = panel_bgr.shape[0]

    panel_y = int(img_h * top_offset_frac)
    panel_x = int(10 * scale_factor) if side == "left" else img_w - panel_w - int(10 * scale_factor)

    # Clip to frame bounds (defensive -- a very tall panel on a small frame shouldn't crash)
    y_end = min(panel_y + panel_h, img_h)
    x_end = min(panel_x + panel_w, img_w)
    if panel_y >= y_end or panel_x >= x_end:
        return
    frame[panel_y:y_end, panel_x:x_end] = panel_bgr[: y_end - panel_y, : x_end - panel_x]


def draw_machine_card(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    machine_name: str,
    machine_id: str,
    telemetry: Optional[Dict[str, Any]],
    production_pct: float = 0.0,
    parts: Optional[List[Dict[str, Any]]] = None,
    next_maintenance_due: str = "TBD",
    fault_reason: str = "TBD",
    operator_name: Optional[str] = None,
    connected: bool = True
) -> None:
    """Draw machine status/maintenance info as fixed left/right HUD side panels, keeping
    the center of the frame clear for the camera view, plus a small reticle on the
    marker itself so it's still clear what's being tracked.

    Args:
        frame: BGR image array to draw onto.
        bbox: Marker bounding box tuple `(x, y, w, h)`.
        machine_name: Human-readable machine name from the machinery database.
        machine_id: Short machine ID from the machinery database (e.g. "MCH-001").
        telemetry: `{"status", "running_hours", "stopped_hours"}` from the machine's
            MQTT telemetry client, or None if no status message has ever arrived.
        production_pct: Placeholder production percentage (not live MQTT data).
        parts: Placeholder list of `{"name", "life_pct", "needs_change"}` dicts.
        next_maintenance_due: Placeholder maintenance-due date/text.
        fault_reason: Placeholder fault reason, shown only when status is STOPPED.
        operator_name: Name of a recognized employee currently in frame with the machine,
            or None if nobody recognized is present.
        connected: Whether a status message has arrived recently (MQTT live).
    """
    x, y, w, h = bbox
    accent_color = COLOR_ORANGE if connected else COLOR_AMBER

    # Small reticle on the marker itself (unobtrusive -- the detailed info lives in the
    # side panels, not a card overlapping the machine/camera view here).
    line_len = max(10, min(w, h) // 4)
    thickness = 2
    cv2.line(frame, (x, y), (x + line_len, y), accent_color, thickness)
    cv2.line(frame, (x, y), (x, y + line_len), accent_color, thickness)
    cv2.line(frame, (x + w, y), (x + w - line_len, y), accent_color, thickness)
    cv2.line(frame, (x + w, y), (x + w, y + line_len), accent_color, thickness)
    cv2.line(frame, (x, y + h), (x + line_len, y + h), accent_color, thickness)
    cv2.line(frame, (x, y + h), (x, y + h - line_len), accent_color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w - line_len, y + h), accent_color, thickness)
    cv2.line(frame, (x + w, y + h), (x + w, y + h - line_len), accent_color, thickness)

    accent_rgb = accent_color[::-1]  # BGR -> RGB for the PIL-rendered panels

    status: Optional[str] = None
    left_kv: List[Tuple[str, str, Tuple[int, int, int]]] = [("ID", machine_id, PANEL_WHITE)]
    if not connected or telemetry is None:
        badge = ("NO SIGNAL", PANEL_AMBER)
        left_kv.append(("LINK", "MQTT unreachable", PANEL_AMBER))
    else:
        status = telemetry.get("status", "UNKNOWN")
        badge = (status, PANEL_GREEN if status == "RUNNING" else PANEL_RED)
        running_h = telemetry.get("running_hours", 0.0)
        stopped_h = telemetry.get("stopped_hours", 0.0)
        left_kv.append(("RUN", f"{running_h:.1f}h", PANEL_CYAN))
        left_kv.append(("DOWN", f"{stopped_h:.1f}h", PANEL_CYAN))

    bottles_filled = telemetry.get("bottles_filled", 0.0) if telemetry else 0.0
    right_kv: List[Tuple[str, str, Tuple[int, int, int]]] = [
        ("PRODUCTION", f"{production_pct:.0f}%", PANEL_GREEN),
        ("BOTTLES FILLED", f"{bottles_filled:.0f}", PANEL_CYAN),
        ("MAINT DUE", next_maintenance_due, PANEL_GREEN),
    ]
    needs_change = [p.get("name", "?") for p in (parts or []) if p.get("needs_change")]
    if needs_change:
        right_kv.append(("PARTS DUE", str(len(needs_change)), PANEL_AMBER))
        for part_name in needs_change[:3]:
            right_kv.append(("", part_name, PANEL_AMBER))
    else:
        right_kv.append(("PARTS", "OK", PANEL_GREEN))
    if operator_name:
        right_kv.append(("OPERATOR", operator_name, PANEL_WHITE))
    if status == "STOPPED" and fault_reason and fault_reason != "TBD":
        right_kv.append(("FAULT", fault_reason, PANEL_RED))

    draw_side_panel(
        frame, title="Machine", side="left", accent_rgb=accent_rgb,
        subtitle=machine_name, badge=badge, kv_rows=left_kv
    )
    draw_side_panel(
        frame, title="Production", side="right", accent_rgb=accent_rgb,
        kv_rows=right_kv
    )


def draw_fps_counter(frame: np.ndarray, fps: float) -> None:
    img_h, img_w = frame.shape[:2]
    scale_factor = img_w / 640.0
    fps_text = f"HUD FPS: {fps:.1f}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, fps_text, (int(15*scale_factor), int(25*scale_factor)), font, 0.5 * scale_factor, COLOR_GREEN, int(1 * scale_factor) or 1, cv2.LINE_AA)


def draw_overlay(
    frame: np.ndarray,
    tracked_faces: List[Dict[str, Any]],
    tracked_machines: Optional[List[Dict[str, Any]]] = None,
    fps: Optional[float] = None
) -> np.ndarray:
    """Render bounding boxes, HUD info cards, and status overlay onto video frame.

    Args:
        frame: Input frame image (BGR numpy array).
        tracked_faces: List of dictionaries containing bbox, match info, and status.
        tracked_machines: List of dictionaries containing bbox, machine info, live telemetry,
            and operator name for detected ArUco-tagged machines.
        fps: Optional current pipeline FPS rate.

    Returns:
        Frame with HUD overlays rendered.
    """
    if frame is None:
        return frame

    # Draw face cards
    for face in tracked_faces:
        bbox = face.get("bbox")
        if bbox is None:
            continue

        match_info = face.get("match")
        if match_info:
            draw_hud_card(
                frame,
                bbox,
                name=match_info.get("name", "Unknown"),
                role=match_info.get("role", "N/A"),
                emp_id=str(match_info.get("id", "N/A")),
                similarity=float(match_info.get("similarity", 0.0)),
                is_known=True
            )
        else:
            draw_hud_card(
                frame,
                bbox,
                name="Unknown",
                role="Unknown",
                emp_id="N/A",
                similarity=0.0,
                is_known=False
            )

    # Draw machine telemetry cards
    for machine in (tracked_machines or []):
        bbox = machine.get("bbox")
        if bbox is None:
            continue

        draw_machine_card(
            frame,
            bbox,
            machine_name=machine.get("name", "Unknown Machine"),
            machine_id=machine.get("machine_id", "N/A"),
            telemetry=machine.get("telemetry"),
            production_pct=machine.get("production_pct", 0.0),
            parts=machine.get("parts"),
            next_maintenance_due=machine.get("next_maintenance_due", "TBD"),
            fault_reason=machine.get("fault_reason", "TBD"),
            operator_name=machine.get("operator_name"),
            connected=machine.get("connected", False)
        )

    # Render FPS counter if provided
    if fps is not None:
        draw_fps_counter(frame, fps)

    return frame
