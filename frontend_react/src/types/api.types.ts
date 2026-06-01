export interface StreetGeometry {
  street_id: number;
  street_name: string;
  district_name: string;
  max_speed: number;
  lat: number;
  lon: number;
  path: [number, number][];
}

export interface TrafficState {
  street_id: number;
  congestion_level: 0 | 1 | 2 | null; // 0=clear, 1=slow, 2=congested
  avg_speed: number;
  max_speed: number;
  timestamp: string; // ISO UTC
}

export interface Incident {
  id: number;
  street_id: number;
  type: 'roadblock' | 'accident' | 'event' | 'community';
  status: 'active' | 'dispatched' | 'resolved' | 'declined';
  severity: 1 | 2 | 3;
  description: string | null;
  start_time: string;
  end_time: string | null;
  is_active: boolean;
  officer_id?: number | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'admin' | 'csgt' | 'user';
  is_active: boolean;
  is_locked: boolean;
  is_busy: boolean;
}

export interface RouteResult {
  path: [number, number][];
  total_distance_m: number;
  estimated_time_min: number;
  streets: {
    name: string;
    congestion_level: number;
    avg_speed: number;
    lat?: number;
    lng?: number;
    path?: [number, number][];
  }[];
}
