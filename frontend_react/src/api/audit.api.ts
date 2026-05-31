import api from '../lib/axios';

export interface AuditLog {
  id: number;
  user_id?: number;
  action: string;
  target_table?: string;
  target_id?: number;
  detail?: any;
  ip_address?: string;
  created_at: string;
  user?: {
    id: number;
    email: string;
    full_name?: string;
    role: string;
  };
}

export const auditApi = {
  getLogs: async (limit: number = 50, offset: number = 0): Promise<AuditLog[]> => {
    const response = await api.get<AuditLog[]>('/api/admin/audit-logs', {
      params: { limit, offset },
    });
    return response.data;
  },
};
