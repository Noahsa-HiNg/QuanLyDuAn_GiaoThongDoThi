import api from '../lib/axios';

export interface CommunityReport {
  id: number;
  latitude: number;
  longitude: number;
  severity: number;
  description?: string;
  is_verified: boolean;
  street_id?: number;
  reported_at: string;
}

export const communityApi = {
  createReport: async (
    latitude: number,
    longitude: number,
    severity: number,
    description?: string
  ): Promise<CommunityReport> => {
    const response = await api.post<CommunityReport>('/api/community/report', {
      latitude,
      longitude,
      severity,
      description,
    });
    return response.data;
  },
  getReports: async (): Promise<CommunityReport[]> => {
    const response = await api.get<CommunityReport[]>('/api/community/reports');
    return response.data;
  },
};
