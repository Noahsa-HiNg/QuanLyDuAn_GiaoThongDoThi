import api from '../lib/axios';

export interface ScheduleState {
  running: boolean;
  paused: boolean;
}

export interface ScheduleJob {
  id: string;
  name: string;
  next_run_time: string | null;
  trigger: string;
}

export interface CrawlStatus {
  last_run: string | null;
  status: string;
  streets_updated: number;
}

export const schedulerApi = {
  getState: async (): Promise<ScheduleState> => {
    const response = await api.get<ScheduleState>('/api/traffic/schedule/state');
    return response.data;
  },
  getJobs: async (): Promise<ScheduleJob[]> => {
    const response = await api.get<ScheduleJob[]>('/api/traffic/schedule/jobs');
    return response.data;
  },
  pauseSchedule: async (): Promise<{ ok: boolean; data?: any }> => {
    const response = await api.post('/api/traffic/schedule/pause');
    return { ok: true, data: response.data };
  },
  resumeSchedule: async (): Promise<{ ok: boolean; data?: any }> => {
    const response = await api.post('/api/traffic/schedule/resume');
    return { ok: true, data: response.data };
  },
  crawlNow: async (): Promise<{ ok: boolean; data?: any }> => {
    const response = await api.post('/api/traffic/crawl', null, { timeout: 60000 });
    return { ok: true, data: response.data };
  },
  getCrawlStatus: async (): Promise<CrawlStatus> => {
    const response = await api.get<CrawlStatus>('/api/traffic/crawl/status');
    return response.data;
  },
  getCrawlLogs: async (limit: number = 150): Promise<{ logs: string[]; total_lines: number; returned_lines: number }> => {
    const response = await api.get(`/api/traffic/crawl/logs?limit=${limit}`);
    return response.data;
  },
  getCrawlStats: async (): Promise<CrawlStatsResponse> => {
    const response = await api.get<CrawlStatsResponse>('/api/traffic/crawl/stats');
    return response.data;
  },
};

export interface CrawlKPIs {
  total_runs: number;
  success_runs: number;
  failed_runs: number;
  missed_runs: number;
  success_rate: number;
  avg_duration: number;
}

export interface DetailedRun {
  timestamp: string;
  date: string;
  status: string;
  success_count: number;
  total_count: number;
  duration: number;
  missed_before: number;
}

export interface DailyStat {
  date: string;
  success: number;
  failed: number;
  missed: number;
}

export interface CrawlStatsResponse {
  success: boolean;
  message?: string;
  kpis: CrawlKPIs;
  last_runs: DetailedRun[];
  daily_stats: DailyStat[];
}
