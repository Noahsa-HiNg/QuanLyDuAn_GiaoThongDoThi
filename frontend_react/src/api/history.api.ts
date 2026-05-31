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
  getPrediction5Min: async (): Promise<any[]> => {
    const response = await api.get<any[]>('/api/predict/5min');
    return response.data;
  },
};
