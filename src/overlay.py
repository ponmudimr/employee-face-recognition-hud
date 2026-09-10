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


def draw_machine_card(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    machine_name: str,
    telemetry: Optional[Dict[str, Any]],
    operator_name: Optional[str] = None,
    connected: bool = True
) -> None:
    """Draw a semi-transparent HUD card with live machine telemetry above/beside its marker.

    Args:
        frame: BGR image array to draw onto.
        bbox: Marker bounding box tuple `(x, y, w, h)`.
        machine_name: Human-readable machine name from the machinery database.
        telemetry: Latest `/api/state` snapshot from the machine's backend, or None if it
            has never been reached.
        operator_name: Name of a recognized employee currently in frame with the machine,
            or None if nobody recognized is present.
        connected: Whether the telemetry backend is currently reachable.
    """
    x, y, w, h = bbox
    accent_color = COLOR_ORANGE if connected else COLOR_AMBER

    # Draw bounding box corner reticles, same style as face cards for a consistent HUD look
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

    img_h, img_w = frame.shape[:2]
    scale_factor = img_w / 640.0

    # Build card text lines from the selected telemetry fields (phase/progress, production,
    # operator) -- a curated subset, not the full BottleWise dashboard.
    lines: List[Tuple[str, Tuple[int, int, int]]] = [(f"MACHINE: {machine_name}", COLOR_WHITE)]

    if not connected or telemetry is None:
        lines.append(("NO TELEMETRY (backend unreachable)", COLOR_AMBER))
    else:
        phase = telemetry.get("phase", "Unknown")
        elapsed = telemetry.get("phase_elapsed_s")
        cycle_time = telemetry.get("cycle_time_s")
        if elapsed is not None and cycle_time is not None:
            lines.append((f"PHASE: {phase} ({elapsed:.0f}s/{cycle_time:.0f}s)", COLOR_CYAN))
        else:
            lines.append((f"PHASE: {phase}", COLOR_CYAN))

        completed = telemetry.get("completedCount")
        in_progress = telemetry.get("inProduction")
        batch_id = telemetry.get("batch_id", "N/A")
        if completed is not None and in_progress is not None:
            lines.append((f"PROD: {completed} done, {in_progress} in-prog | {batch_id}", COLOR_GREEN))
        else:
            lines.append((f"BATCH: {batch_id}", COLOR_GREEN))

    if operator_name:
        lines.append((f"OPERATOR: {operator_name}", COLOR_WHITE))

    line_h = int(18 * scale_factor)
    card_w = int(max(260 * scale_factor, w + (40 * scale_factor)))
    card_h = int(10 * scale_factor) + line_h * len(lines)
    card_x = max(5, x)
    card_y = max(5, y - card_h - int(10 * scale_factor))
    if card_y < 0:
        card_y = y + h + int(10 * scale_factor)
    if card_x + card_w > img_w:
        card_x = max(5, img_w - card_w - 5)

    overlay = frame.copy()
    cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), COLOR_BG_DARK, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), accent_color, int(1 * scale_factor) or 1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45 * scale_factor
    th = int(1 * scale_factor) or 1
    for i, (text, color) in enumerate(lines):
        text_y = card_y + int(18 * scale_factor) + i * line_h
        cv2.putText(frame, text, (card_x + int(8 * scale_factor), text_y), font, font_scale, color, th)


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
            telemetry=machine.get("telemetry"),
            operator_name=machine.get("operator_name"),
            connected=machine.get("connected", False)
        )

    # Render FPS counter if provided
    if fps is not None:
        draw_fps_counter(frame, fps)

    return frame
