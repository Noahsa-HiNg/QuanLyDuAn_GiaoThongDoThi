import { useQuery } from '@tanstack/react-query';
import { trafficApi } from '../api/traffic.api';
import type { GeometryResponse } from '../api/traffic.api';

const GEOMETRY_TTL = 3600_000; // 1h

export function useGeometry() {
  return useQuery<GeometryResponse>({
    queryKey: ['geometry'],
    queryFn: () => trafficApi.getGeometry(),
    staleTime: GEOMETRY_TTL,
  });
}
