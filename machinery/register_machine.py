"""CLI Registration Tool: Assigns an ArUco marker ID to a machine, saves it to the local JSON
database, and generates a printable marker image to stick on the physical machine/PLC panel.
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


def save_machine_record(
    db_path: str,
    marker_id: int,
    name: str,
    api_base_url: str
) -> bool:
    """Save or update a machine record in the local JSON database file.

    Args:
        db_path: Path to database JSON file.
        marker_id: ArUco marker ID assigned to this machine.
        name: Human-readable machine name.
        api_base_url: Base URL of the machine's telemetry backend (e.g. BottleWise's
            Node.js server), without a trailing `/api/state`.

    Returns:
        bool: True if saved successfully, False otherwise.
    """
    database: List[Dict[str, Any]] = load_machine_database(db_path)

    new_record = {
        "marker_id": marker_id,
        "name": name,
        "api_base_url": api_base_url
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
    parser.add_argument("--api-url", type=str, help="Base URL of the machine's telemetry backend, e.g. http://192.168.1.50:3001")
    parser.add_argument("--db", type=str, default="machinery/database/machines.json", help="Database file output path")
    parser.add_argument("--markers-dir", type=str, default="machinery/markers", help="Directory to save the printable marker PNG into")

    args = parser.parse_args()

    marker_id = args.marker_id if args.marker_id is not None else int(input("Enter ArUco marker ID (0-49): ").strip())
    name = args.name or input("Enter machine name: ").strip()
    api_base_url = args.api_url or input("Enter telemetry backend base URL (e.g. http://192.168.1.50:3001): ").strip()

    if not name or not api_base_url:
        logger.error("Machine name and API base URL are required fields.")
        sys.exit(1)

    if save_machine_record(args.db, marker_id, name, api_base_url):
        marker_path = os.path.join(args.markers_dir, f"marker_{marker_id}.png")
        generate_marker_image(marker_id, marker_path)
        logger.info("Machine registration completed successfully!")
    else:
        logger.error("Machine registration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
