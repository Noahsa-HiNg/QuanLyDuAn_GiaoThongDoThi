import api from '../lib/axios';

export interface TrafficHistoryResponse {
  hours_ago: number;
  target_time: string;
  total: number;
  streets: any[];
}

export const historyApi = {
  getTrafficHistory: async (hoursAgo: number): Promise<TrafficHistoryResponse> => {
    const response = await api.get<TrafficHistoryResponse>(`/api/traffic/history?hours_ago=${hoursAgo}`);
    return response.data;
  },
  getPrediction10Min: async (): Promise<any[]> => {
    const response = await api.get<any[]>('/api/predict/10min');
    return response.data;
  },
  getPrediction20Min: async (): Promise<any[]> => {
    const response = await api.get<any[]>('/api/predict/20min');
    return response.data;
  },
  getPrediction30Min: async (): Promise<any[]> => {
    const response = await api.get<any[]>('/api/predict/30min');
    return response.data;
  },
};
