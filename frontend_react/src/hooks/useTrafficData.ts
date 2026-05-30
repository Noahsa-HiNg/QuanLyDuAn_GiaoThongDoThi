import { useQuery } from '@tanstack/react-query';
import { trafficApi } from '../api/traffic.api';
import type { StateResponse } from '../api/traffic.api';
import { REFRESH_INTERVAL_MS } from '../constants/map.constants';

export function useTrafficData() {
  return useQuery<StateResponse>({
    queryKey: ['traffic-state'],
    queryFn: () => trafficApi.getState(),
    refetchInterval: REFRESH_INTERVAL_MS,
    staleTime: REFRESH_INTERVAL_MS - 10000,
  });
}
