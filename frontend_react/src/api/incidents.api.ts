import api from '../lib/axios';
import type { Incident } from '../types/api.types';

export interface GetIncidentsParams {
  is_active?: boolean;
  type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export interface CreateIncidentData {
  street_id: number;
  type: 'roadblock' | 'accident' | 'event' | 'community';
  severity: number;
  description: string;
  status: 'active' | 'dispatched' | 'resolved';
  is_active: boolean;
}

export const incidentsApi = {
  getIncidents: async (params?: GetIncidentsParams): Promise<Incident[]> => {
    const response = await api.get<Incident[]>('/api/incidents', { params });
    return response.data;
  },
  createIncident: async (data: CreateIncidentData): Promise<{ ok: boolean; data: Incident }> => {
    const response = await api.post<Incident>('/api/incidents', data);
    return { ok: true, data: response.data };
  },
  updateIncidentStatus: async (incidentId: number, status: string): Promise<{ ok: boolean }> => {
    await api.put(`/api/incidents/${incidentId}`, { status });
    return { ok: true };
  },
  deleteIncident: async (incidentId: number): Promise<{ ok: boolean }> => {
    await api.delete(`/api/incidents/${incidentId}`);
    return { ok: true };
  },
};
