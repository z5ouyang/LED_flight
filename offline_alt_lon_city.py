from __future__ import annotations

import csv
import json
import logging
from io import StringIO

import requests

import kdnode as kd

logger = logging.getLogger(__name__)

iata_url = (
    "https://raw.githubusercontent.com/davidmegginson/"
    "ourairports-data/refs/heads/main/airports.csv"
)


def main() -> None:
    airport_info: list[list[float | str]] = []
    airport_us_info: list[list[float | str]] = []

    iata_io = requests.get(iata_url, timeout=30)
    iata_info = list(csv.DictReader(StringIO(iata_io.text)))
    for _i, row in enumerate(iata_info):
        if len(row["iata_code"]) != 3:
            continue
        airport_info.append(
            [
                float(row["latitude_deg"]),
                float(row["longitude_deg"]),
                row["iata_code"],
                row["municipality"] + "," + row["iso_region"],
            ]
        )
        if row["iso_region"].startswith("US"):
            airport_us_info.append(
                [
                    float(row["latitude_deg"]),
                    float(row["longitude_deg"]),
                    row["iata_code"],
                    row["municipality"] + "," + row["iso_region"],
                ]
            )
    logger.info(
        "Total number of IATA airports: %d",
        len(airport_info),
    )
    logger.info(
        "Total number of US IATA airports: %d",
        len(airport_us_info),
    )
    airport_info_tree = kd.build_kdtree(airport_info)
    with open("iata_info.json", "w") as f:
        json.dump(kd.node_to_dict(airport_info_tree), f)

    airport_us_tree = kd.build_kdtree(airport_us_info)
    with open("iata_us_info.json", "w") as f:
        json.dump(kd.node_to_dict(airport_us_tree), f)


if __name__ == "__main__":
    main()
