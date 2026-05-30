export const DA_NANG_CENTER: [number, number] = [108.2022, 16.0544]; // [lng, lat]
export const DEFAULT_ZOOM = 13;
export const REFRESH_INTERVAL_MS = 240_000; // 4 phút

export const CONGESTION_COLORS: Record<number | string, string> = {
  0: '#22c55e',
  1: '#f59e0b',
  2: '#ef4444',
  'null': '#94a3b8',
};

export const DISTRICT_OPTIONS = [
  { id: null, label: '🗺️ Tất cả quận/huyện' },
  { id: 1, label: 'Hải Châu' },
  { id: 2, label: 'Thanh Khê' },
  { id: 3, label: 'Sơn Trà' },
  { id: 4, label: 'Ngũ Hành Sơn' },
  { id: 5, label: 'Liên Chiểu' },
  { id: 6, label: 'Cẩm Lệ' },
  { id: 7, label: 'Hòa Vang' },
  { id: 8, label: 'Hoàng Sa' },
];
