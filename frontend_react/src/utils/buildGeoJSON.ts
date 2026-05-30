import type { StreetGeometry, TrafficState } from '../types/api.types';

interface GeometryResponse {
  streets: StreetGeometry[];
}
interface StateResponse {
  streets: TrafficState[];
  data_as_of: string | null;
}

export function buildGeoJSON(
  geometry: GeometryResponse,
  state: StateResponse
): GeoJSON.FeatureCollection {
  const stateMap = new Map<number, TrafficState>();
  for (const s of state.streets ?? []) {
    stateMap.set(s.street_id, s);
  }

  const features: GeoJSON.Feature[] = (geometry.streets ?? []).map(street => {
    const traffic = stateMap.get(street.street_id);
    return {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: street.path ?? [],
      },
      properties: {
        street_id: street.street_id,
        name: street.street_name,
        district: street.district_name,
        congestion_level: traffic?.congestion_level !== undefined ? traffic.congestion_level : null,
        avg_speed: traffic?.avg_speed ?? null,
        max_speed: street.max_speed ?? traffic?.max_speed ?? null,
        timestamp: traffic?.timestamp ?? null,
      },
    };
  });

  return { type: 'FeatureCollection', features };
}
