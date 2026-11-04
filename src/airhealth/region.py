"""Spatial domain definitions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """Geographic bounding box in decimal degrees (WGS84).

    Order follows the Copernicus convention: north, west, south, east.
    """

    north: float
    west: float
    south: float
    east: float

    def __post_init__(self) -> None:
        if not -90 <= self.south < self.north <= 90:
            raise ValueError(f"Invalid latitudes: south={self.south}, north={self.north}")
        if not (-180 <= self.west <= 180 and -180 <= self.east <= 180):
            raise ValueError(f"Invalid longitudes: west={self.west}, east={self.east}")

    @classmethod
    def around(cls, lat: float, lon: float, half_width_deg: float = 1.0) -> "BoundingBox":
        """Square box centred on a point."""
        return cls(
            north=min(lat + half_width_deg, 90.0),
            west=max(lon - half_width_deg, -180.0),
            south=max(lat - half_width_deg, -90.0),
            east=min(lon + half_width_deg, 180.0),
        )

    def as_cds_area(self) -> list[float]:
        """Return the ``area`` list expected by the Copernicus CDS/ADS API."""
        return [self.north, self.west, self.south, self.east]

    def tag(self) -> str:
        """Short, filesystem-safe identifier for file names."""
        return f"N{self.north:g}_W{self.west:g}_S{self.south:g}_E{self.east:g}".replace("-", "m")


GLOBAL = BoundingBox(north=90, west=-180, south=-90, east=180)
