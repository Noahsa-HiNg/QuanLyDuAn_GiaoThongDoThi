const getBackendUrl = () => {
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return import.meta.env.VITE_API_BASE || 'http://localhost:8000';
  }
  return `http://${hostname}:8000`;
};

export const BACKEND_URL = getBackendUrl();
export const REQUEST_TIMEOUT = 10000; // 10s
