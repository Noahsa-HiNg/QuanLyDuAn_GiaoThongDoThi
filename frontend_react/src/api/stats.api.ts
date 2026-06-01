import api from '../lib/axios';

export interface CongestedStreet {
  street_name: string;
  district_name: string;
  avg_speed: number;
}

export interface StatsReport {
  avg_speed: number;
  red_count: number;
  yellow_count: number;
  green_count: number;
  top_congested: CongestedStreet[];
}

export interface HourlyTrend {
  hour: number;
  avg_congestion_pct: number;
  avg_speed: number;
}

export interface HeatmapItem {
  hour: number;
  weekday: number;
  congestion_pct: number;
}

export interface WeatherCurrent {
  temperature: number;
  humidity: number;
  wind_speed: number;
  rain_1h_mm: number;
  is_raining: boolean;
  weather_group: string;
}

export interface IncidentStats {
  total_active: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  avg_resolve_time_minutes: number;
}

export interface TopReportedStreet {
  street_name: string;
  report_count: number;
}

export interface FeedbackStats {
  total_reports: number;
  by_type: Record<string, number>;
  top_reported_streets: TopReportedStreet[];
}

export interface PredictedRecord {
  road_id: number;
  road_name: string;
  lat: number | null;
  lng: number | null;
  predicted_level: number; // 1=xanh, 2=vàng, 3=đỏ
  confidence: number;
  predicted_at: string;
}

export const statsApi = {
  getReport: async (): Promise<StatsReport> => {
    const response = await api.get<StatsReport>('/api/stats/report');
    return response.data;
  },
  getHourlyTrend: async (days: number = 7): Promise<HourlyTrend[]> => {
    const response = await api.get<HourlyTrend[]>('/api/stats/hourly-trend', { params: { days } });
    return response.data;
  },
  getHeatmap: async (days: number = 30): Promise<HeatmapItem[]> => {
    const response = await api.get<HeatmapItem[]>('/api/stats/heatmap', { params: { days } });
    return response.data;
  },
  getWeatherCurrent: async (): Promise<WeatherCurrent> => {
    const response = await api.get<WeatherCurrent>('/api/weather/current');
    return response.data;
  },
  getIncidentStats: async (): Promise<IncidentStats> => {
    const response = await api.get<IncidentStats>('/api/stats/incidents');
    return response.data;
  },
  getFeedbackSummary: async (): Promise<FeedbackStats> => {
    const response = await api.get<FeedbackStats>('/api/stats/feedback-summary');
    return response.data;
  },
  getPredictions: async (): Promise<PredictedRecord[]> => {
    const response = await api.get<PredictedRecord[]>('/api/predict/30min');
    return response.data;
  },
};

