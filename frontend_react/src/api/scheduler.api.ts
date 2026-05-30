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
};
