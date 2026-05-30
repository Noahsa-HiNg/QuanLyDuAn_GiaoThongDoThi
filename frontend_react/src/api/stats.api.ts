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

export const statsApi = {
  getReport: async (): Promise<StatsReport> => {
    const response = await api.get<StatsReport>('/api/stats/report');
    return response.data;
  },
  getHourlyTrend: async (days: number = 7): Promise<HourlyTrend[]> => {
    const response = await api.get<HourlyTrend[]>('/api/stats/hourly-trend', { params: { days } });
    return response.data;
  },
  getHeatmap: async (): Promise<HeatmapItem[]> => {
    const response = await api.get<HeatmapItem[]>('/api/stats/heatmap');
    return response.data;
  },
  getWeatherCurrent: async (): Promise<WeatherCurrent> => {
    const response = await api.get<WeatherCurrent>('/api/weather/current');
    return response.data;
  },
};
