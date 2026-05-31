import api from '../lib/axios';

export interface EmergencyBanner {
  id: number;
  title: string;
  content: string;
  is_active: boolean;
  created_at: string;
  expires_at?: string;
}

export const emergencyApi = {
  createAlert: async (
    title: string,
    content: string,
    expires_at?: string
  ): Promise<EmergencyBanner> => {
    const response = await api.post<EmergencyBanner>('/api/system/announcement', {
      title,
      content,
      is_active: true,
      expires_at,
    });
    return response.data;
  },
  getActiveAlert: async (): Promise<EmergencyBanner | null> => {
    const response = await api.get<EmergencyBanner | null>('/api/system/announcement');
    return response.data;
  },
  getAlertList: async (): Promise<EmergencyBanner[]> => {
    const response = await api.get<EmergencyBanner[]>('/api/system/announcement/list');
    return response.data;
  },
  deactivateAlert: async (alertId: number): Promise<EmergencyBanner> => {
    const response = await api.post<EmergencyBanner>(`/api/system/announcement/${alertId}/deactivate`);
    return response.data;
  },
};
