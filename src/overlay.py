"""HUD graphic overlay rendering for AR glass display using OpenCV drawing functions."""

from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

# HUD Theme Colors (BGR format)
COLOR_CYAN = (255, 255, 0)
COLOR_GREEN = (0, 255, 128)
COLOR_AMBER = (0, 165, 255)
COLOR_RED = (0, 0, 255)
COLOR_BG_DARK = (20, 20, 20)
COLOR_WHITE = (255, 255, 255)
COLOR_ORANGE = (0, 140, 255)  # industrial accent, visually distinct from person cards


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


def draw_side_panel(
    frame: np.ndarray,
    lines: List[Tuple[str, Tuple[int, int, int]]],
    side: str,
    accent_color: Tuple[int, int, int],
    top_offset_frac: float = 0.10
) -> None:
    """Draw a semi-transparent HUD info panel anchored to the left or right edge of the
    frame, so the center stays clear for the camera view (a fixed sci-fi-HUD layout
    rather than a card that follows the tracked object around and can obscure it).

    Args:
        frame: BGR image array to draw onto.
        lines: List of `(text, color)` tuples, one per line, top to bottom.
        side: `"left"` or `"right"` -- which edge to anchor to.
        accent_color: Border/accent color for this panel.
        top_offset_frac: Vertical start position as a fraction of frame height.
    """
    if not lines:
        return

    img_h, img_w = frame.shape[:2]
    scale_factor = img_w / 640.0

    line_h = int(20 * scale_factor)
    panel_w = int(215 * scale_factor)
    panel_h = int(12 * scale_factor) + line_h * len(lines)
    panel_y = int(img_h * top_offset_frac)
    panel_x = int(10 * scale_factor) if side == "left" else img_w - panel_w - int(10 * scale_factor)

    overlay = frame.copy()
    cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), COLOR_BG_DARK, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), accent_color, int(1 * scale_factor) or 1)

    # Thicker accent line on the inner edge (facing the center) for a HUD look
    inner_x = panel_x + panel_w if side == "left" else panel_x
    cv2.line(frame, (inner_x, panel_y), (inner_x, panel_y + panel_h), accent_color, int(2 * scale_factor) or 2)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45 * scale_factor
    th = int(1 * scale_factor) or 1
    for i, (text, color) in enumerate(lines):
        text_y = panel_y + int(20 * scale_factor) + i * line_h
        cv2.putText(frame, text, (panel_x + int(8 * scale_factor), text_y), font, font_scale, color, th)


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

    status: Optional[str] = None
    left_lines: List[Tuple[str, Tuple[int, int, int]]] = [
        (f"MACHINE: {machine_name}", COLOR_WHITE),
        (f"ID: {machine_id}", COLOR_WHITE),
    ]
    if not connected or telemetry is None:
        left_lines.append(("NO LIVE STATUS", COLOR_AMBER))
        left_lines.append(("(MQTT unreachable)", COLOR_AMBER))
    else:
        status = telemetry.get("status", "UNKNOWN")
        status_color = COLOR_GREEN if status == "RUNNING" else COLOR_RED
        left_lines.append((f"STATUS: {status}", status_color))
        running_h = telemetry.get("running_hours", 0.0)
        stopped_h = telemetry.get("stopped_hours", 0.0)
        left_lines.append((f"RUN:  {running_h:.1f}h", COLOR_CYAN))
        left_lines.append((f"DOWN: {stopped_h:.1f}h", COLOR_CYAN))

    right_lines: List[Tuple[str, Tuple[int, int, int]]] = [
        (f"PROD: {production_pct:.0f}%", COLOR_GREEN),
        (f"MAINT DUE: {next_maintenance_due}", COLOR_GREEN),
    ]
    needs_change = [p.get("name", "?") for p in (parts or []) if p.get("needs_change")]
    if needs_change:
        right_lines.append(("PARTS DUE:", COLOR_AMBER))
        for part_name in needs_change:
            right_lines.append((f"  {part_name}", COLOR_AMBER))
    else:
        right_lines.append(("PARTS: OK", COLOR_GREEN))
    if operator_name:
        right_lines.append((f"OPERATOR: {operator_name}", COLOR_WHITE))
    if status == "STOPPED" and fault_reason and fault_reason != "TBD":
        right_lines.append((f"FAULT: {fault_reason}", COLOR_RED))

    draw_side_panel(frame, left_lines, side="left", accent_color=accent_color)
    draw_side_panel(frame, right_lines, side="right", accent_color=accent_color)


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
