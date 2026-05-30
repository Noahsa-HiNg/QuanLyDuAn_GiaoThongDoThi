import api from '../lib/axios';
import type { RouteResult } from '../types/api.types';

export interface StreetMidpoint {
  id: number;
  name: string;
  lat: number;
  lng: number;
}

export const routingApi = {
  getMidpoints: async (): Promise<StreetMidpoint[]> => {
    const response = await api.get<{ streets: StreetMidpoint[] }>('/api/streets/midpoints');
    return response.data.streets;
  },
  getRoute: async (
    fromLat: number,
    fromLng: number,
    toLat: number,
    toLng: number,
    mode: 'shortest' | 'fastest' = 'shortest'
  ): Promise<RouteResult> => {
    const response = await api.get<RouteResult>('/api/routes', {
      params: {
        from_lat: fromLat,
        from_lng: fromLng,
        to_lat: toLat,
        to_lng: toLng,
        mode,
      },
    });
    return response.data;
  },
};
