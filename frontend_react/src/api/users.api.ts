import api from '../lib/axios';
import type { User } from '../types/api.types';

export const usersApi = {
  getUsers: async (): Promise<User[]> => {
    const response = await api.get<User[]>('/api/users');
    return response.data;
  },
  createUser: async (data: Partial<User> & { password?: string }): Promise<{ ok: boolean; data: User }> => {
    const response = await api.post<User>('/api/users', data);
    return { ok: true, data: response.data };
  },
  lockUser: async (userId: number): Promise<{ ok: boolean }> => {
    await api.post(`/api/users/${userId}/lock`);
    return { ok: true };
  },
  unlockUser: async (userId: number): Promise<{ ok: boolean }> => {
    await api.post(`/api/users/${userId}/unlock`);
    return { ok: true };
  },
  deleteUser: async (userId: number): Promise<{ ok: boolean }> => {
    await api.delete(`/api/users/${userId}`);
    return { ok: true };
  },
  getOfficers: async (): Promise<User[]> => {
    const response = await api.get<User[]>('/api/users/officers');
    return response.data;
  },
};
