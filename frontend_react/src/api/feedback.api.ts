// frontend_react/src/api/feedback.api.ts
import api from '../lib/axios';

export interface FeedbackData {
  street_id?: number | null;
  lat: number;
  lon: number;
  report_type: 'congested' | 'clear' | 'accident';
  description?: string;
}

export const feedbackApi = {
  createFeedback: async (data: FeedbackData): Promise<{ id: number; created_at: string }> => {
    const response = await api.post<{ id: number; created_at: string }>('/api/feedback', data);
    return response.data;
  },
};
