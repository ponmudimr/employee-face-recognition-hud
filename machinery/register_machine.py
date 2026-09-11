"""CLI Registration Tool: Assigns an ArUco marker ID to a machine, saves it to the local JSON
database, and generates a printable marker image to stick on the physical machine/PLC panel.

Only `status_topic` (running/stopped) is real MQTT data the HUD subscribes to at runtime;
running_hours/stopped_hours are derived locally from it (see machine_telemetry.py).
Everything else here (production_pct, parts, next_maintenance_due, fault_reason) is static
placeholder data shown as-is on the HUD card -- edit machines.json by hand to update it.
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from machine_detect import DEFAULT_ARUCO_DICT, load_machine_database

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Machine-Register")

DEFAULT_MQTT_BROKER = "broker.hivemq.com"
DEFAULT_MQTT_PORT = 1883
DEFAULT_STATUS_TOPIC = "bottlewise/conveyor/input/state"


def save_machine_record(
    db_path: str,
    marker_id: int,
    name: str,
    machine_id: str,
    mqtt_broker: str = DEFAULT_MQTT_BROKER,
    mqtt_port: int = DEFAULT_MQTT_PORT,
    status_topic: str = DEFAULT_STATUS_TOPIC,
    production_pct: float = 0.0,
    parts: List[Dict[str, Any]] = None,
    next_maintenance_due: str = "TBD",
    fault_reason: str = "TBD"
) -> bool:
    """Save or update a machine record in the local JSON database file.

    Args:
        db_path: Path to database JSON file.
        marker_id: ArUco marker ID assigned to this machine.
        name: Human-readable machine name.
        machine_id: Short machine identifier shown on the HUD card (e.g. "MCH-001").
        mqtt_broker: MQTT broker hostname the machine's PLC/sensors publish to.
        mqtt_port: MQTT broker port (1883 for plain TCP).
        status_topic: MQTT topic whose payload indicates running/stopped state.
        production_pct: Placeholder production percentage shown on the card.
        parts: Placeholder list of {"name", "life_pct", "needs_change"} dicts.
        next_maintenance_due: Placeholder maintenance-due date/text.
        fault_reason: Placeholder fault/alarm reason shown when status is STOPPED.

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    database: List[Dict[str, Any]] = load_machine_database(db_path)

    new_record = {
        "marker_id": marker_id,
        "name": name,
        "machine_id": machine_id,
        "mqtt_broker": mqtt_broker,
        "mqtt_port": mqtt_port,
        "status_topic": status_topic,
        "production_pct": production_pct,
        "parts": parts if parts is not None else [],
        "next_maintenance_due": next_maintenance_due,
        "fault_reason": fault_reason
    }

    updated = False
    for i, rec in enumerate(database):
        if int(rec.get("marker_id", -1)) == marker_id:
            database[i] = new_record
            updated = True
            break
    if not updated:
        database.append(new_record)

    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(database, f, indent=2)
        logger.info(f"Saved machine database to '{db_path}'. Total registered: {len(database)}.")
        return True
    except Exception as e:
        logger.error(f"Failed to write machine database file '{db_path}': {e}")
        return False


def generate_marker_image(marker_id: int, output_path: str, size_px: int = 600) -> None:
    """Render and save a printable ArUco marker PNG for the given ID.

    Args:
        marker_id: ArUco marker ID to render.
        output_path: Filepath to save the marker PNG.
        size_px: Marker image size in pixels (square). 600px prints clearly at a few inches.
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(DEFAULT_ARUCO_DICT)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, size_px)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, marker_img)
    logger.info(f"Saved printable marker image to '{output_path}'. Print it and attach it to the machine.")


def main() -> None:
    """CLI entrypoint for machine registration."""
    parser = argparse.ArgumentParser(description="Register a machine/PLC into the local HUD machinery database")
    parser.add_argument("--marker-id", type=int, help="ArUco marker ID to assign (0-49 for the default 4x4_50 dictionary)")
    parser.add_argument("--name", type=str, help="Human-readable machine name (e.g. 'Bottle Filling Line')")
    parser.add_argument("--machine-id", type=str, help="Short machine ID shown on the card (e.g. 'MCH-001')")
    parser.add_argument("--mqtt-broker", type=str, default=DEFAULT_MQTT_BROKER, help=f"MQTT broker hostname (default: {DEFAULT_MQTT_BROKER})")
    parser.add_argument("--mqtt-port", type=int, default=DEFAULT_MQTT_PORT, help=f"MQTT broker port (default: {DEFAULT_MQTT_PORT})")
    parser.add_argument("--status-topic", type=str, default=DEFAULT_STATUS_TOPIC, help=f"MQTT topic for running/stopped state (default: {DEFAULT_STATUS_TOPIC})")
    parser.add_argument("--production-pct", type=float, default=0.0, help="Placeholder production percentage")
    parser.add_argument("--next-maintenance-due", type=str, default="TBD", help="Placeholder next-maintenance-due date/text")
    parser.add_argument("--fault-reason", type=str, default="TBD", help="Placeholder fault reason shown when stopped")
    parser.add_argument("--db", type=str, default="machinery/database/machines.json", help="Database file output path")
    parser.add_argument("--markers-dir", type=str, default="machinery/markers", help="Directory to save the printable marker PNG into")

    args = parser.parse_args()

    marker_id = args.marker_id if args.marker_id is not None else int(input("Enter ArUco marker ID (0-49): ").strip())
    name = args.name or input("Enter machine name: ").strip()
    machine_id = args.machine_id or input("Enter machine ID (e.g. MCH-001): ").strip()

    if not name or not machine_id:
        logger.error("Machine name and machine ID are required fields.")
        sys.exit(1)

    # Placeholder parts list -- hand-edit machines.json afterward for anything more
    # specific; this is dummy data, not a real maintenance record.
    placeholder_parts = [
        {"name": "Sample Part A", "life_pct": 80, "needs_change": False},
        {"name": "Sample Part B", "life_pct": 15, "needs_change": True}
    ]

    if save_machine_record(
        args.db, marker_id, name, machine_id,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        status_topic=args.status_topic,
        production_pct=args.production_pct,
        parts=placeholder_parts,
        next_maintenance_due=args.next_maintenance_due,
        fault_reason=args.fault_reason
    ):
        marker_path = os.path.join(args.markers_dir, f"marker_{marker_id}.png")
        generate_marker_image(marker_id, marker_path)
        logger.info("Machine registration completed successfully! Edit machines.json by hand to adjust parts/production placeholder data.")
    else:
        logger.error("Machine registration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
