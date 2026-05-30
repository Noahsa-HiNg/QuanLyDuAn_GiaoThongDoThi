import api from '../lib/axios';
import type { StreetGeometry, TrafficState } from '../types/api.types';

export interface GeometryResponse {
  streets: StreetGeometry[];
  total: number;
}

export interface StateResponse {
  streets: TrafficState[];
  total: number;
  data_as_of: string | null;
}

export interface PredictionResponse {
  street_id: number;
  predicted_level: 0 | 1 | 2;
  confidence: number;
}

export const trafficApi = {
  getGeometry: async (): Promise<GeometryResponse> => {
    const response = await api.get<GeometryResponse>('/api/traffic/streets-geometry');
    return response.data;
  },
  getState: async (): Promise<StateResponse> => {
    const response = await api.get<StateResponse>('/api/traffic/state');
    return response.data;
  },
  getCurrent: async (districtId?: number): Promise<StateResponse> => {
    const params = districtId ? { district_id: districtId } : {};
    const response = await api.get<StateResponse>('/api/traffic/current', { params });
    return response.data;
  },
  getPredict30Min: async (): Promise<PredictionResponse[]> => {
    const response = await api.get<PredictionResponse[]>('/api/predict/30min');
    return response.data;
  },
};
