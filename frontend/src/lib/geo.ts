/**
 * Small geo helpers for the map layer. MapLibre's circle layer sizes markers in
 * *pixels*, so to draw a hotspot's true real-world radius (e.g. "744 m") we
 * approximate the circle as a GeoJSON polygon in metres — this way the drawn
 * ring is the actual detection radius, zooming with the map.
 */

import type { Feature, FeatureCollection, Point, Polygon } from "geojson";

const EARTH_RADIUS_M = 6_371_000;

/** GeoJSON polygon approximating a circle of `radiusM` around [lon, lat]. */
export function circlePolygon(
  lat: number,
  lon: number,
  radiusM: number,
  props: Record<string, unknown> = {},
  steps = 64,
): Feature<Polygon> {
  const coords: [number, number][] = [];
  const latR = (lat * Math.PI) / 180;
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * 2 * Math.PI;
    const dLat = (radiusM * Math.cos(theta)) / EARTH_RADIUS_M;
    const dLon = (radiusM * Math.sin(theta)) / (EARTH_RADIUS_M * Math.cos(latR));
    coords.push([lon + (dLon * 180) / Math.PI, lat + (dLat * 180) / Math.PI]);
  }
  return { type: "Feature", geometry: { type: "Polygon", coordinates: [coords] }, properties: props };
}

export function pointFeature(
  lat: number,
  lon: number,
  props: Record<string, unknown> = {},
): Feature<Point> {
  return { type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: props };
}

export function featureCollection<T extends Feature>(features: T[]): FeatureCollection {
  return { type: "FeatureCollection", features };
}
