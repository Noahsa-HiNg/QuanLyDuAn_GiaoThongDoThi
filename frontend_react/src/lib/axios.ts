import axios from 'axios';
import { BACKEND_URL } from '../constants/api.constants';
import { useAuthStore } from '../store/authStore';

const api = axios.create({
  baseURL: BACKEND_URL,
});

// Request interceptor: tự động thêm Bearer token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Response interceptor: 401 → logout
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

export default api;
