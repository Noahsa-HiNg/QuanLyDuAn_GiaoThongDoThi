import api from '../lib/axios';
import type { AuthResponse } from '../types/auth.types';

export const authApi = {
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/api/auth/login', { email, password });
    return response.data;
  },
};
