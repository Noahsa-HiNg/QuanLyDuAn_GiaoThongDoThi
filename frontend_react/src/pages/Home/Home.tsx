import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Menu, X, RotateCcw, AlertTriangle, Thermometer, CloudRain, Shield, RefreshCw } from 'lucide-react';
import TrafficMap from '../../components/map/TrafficMap';
import { trafficApi } from '../../api/traffic.api';
import { incidentsApi } from '../../api/incidents.api';
import { statsApi } from '../../api/stats.api';
import { DISTRICT_OPTIONS } from '../../constants/map.constants';
import { useAuthStore } from '../../store/authStore';

const Home: React.FC = () => {
  const { isLoggedIn, user } = useAuthStore();
  const isCSGTOrAdmin = isLoggedIn && (user?.role === 'csgt' || user?.role === 'admin');

  // Navigation & UI States
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [selectedDistrict, setSelectedDistrict] = useState<number | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isPredictionMode, setIsPredictionMode] = useState(false);

  // Auto-refresh countdown
  const [countdown, setCountdown] = useState(240);

  // Queries
  const { data: trafficState, refetch: refetchTrafficState } = useQuery({
    queryKey: ['traffic-state'],
    queryFn: () => trafficApi.getState(),
  });

  const { data: predictionData } = useQuery({
    queryKey: ['predictions'],
    queryFn: () => trafficApi.getPredict30Min(),
    enabled: isPredictionMode,
  });

  const { data: activeIncidents } = useQuery({
    queryKey: ['active-incidents'],
    queryFn: () => incidentsApi.getIncidents({ is_active: true }),
    refetchInterval: 60000,
    enabled: isCSGTOrAdmin,
  });

  const { data: weather } = useQuery({
    queryKey: ['weather'],
    queryFn: () => statsApi.getWeatherCurrent(),
    refetchInterval: 300000,
  });

  // Countdown logic
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          refetchTrafficState();
          return 240;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [refetchTrafficState]);

  // Calculate live stats
  const totalStreets = trafficState?.total ?? 0;
  const redCount = trafficState?.streets?.filter((s) => s.congestion_level === 2).length ?? 0;
  const yellowCount = trafficState?.streets?.filter((s) => s.congestion_level === 1).length ?? 0;

  const avgSpeed = (() => {
    if (!trafficState?.streets || trafficState.streets.length === 0) return 0;
    const validStreets = trafficState.streets.filter(s => s.avg_speed > 0);
    if (validStreets.length === 0) return 0;
    const sum = validStreets.reduce((acc, s) => acc + s.avg_speed, 0);
    return Math.round(sum / validStreets.length);
  })();

  const activeIncidentCount = activeIncidents?.length ?? 0;

  // Reset Filters
  const handleResetFilters = () => {
    setSelectedDistrict(null);
    setSelectedLevel(null);
    setSearchQuery('');
  };

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* 1. Map container (fills screen) */}
      <div className="absolute inset-0 z-0">
        <TrafficMap
          districtId={selectedDistrict}
          congestionLevel={selectedLevel}
          searchQuery={searchQuery}
          isPredictionMode={isPredictionMode}
          predictionData={predictionData}
        />
      </div>

      {/* 2. Left side filter panel overlay */}
      <div
        className={`absolute top-16 left-0 h-[calc(100vh-64px)] w-80 bg-slate-950/80 backdrop-blur-md border-r border-white/10 shadow-2xl transition-transform duration-300 ease-in-out z-40 flex flex-col ${
          isFilterOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="font-bold text-lg text-white">Bộ lọc giao thông</h2>
          <button
            onClick={() => setIsFilterOpen(false)}
            className="p-1 text-slate-400 hover:text-white transition cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto space-y-6">
          {/* District Filter */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">Quận/Huyện</label>
            <select
              value={selectedDistrict ?? ''}
              onChange={(e) =>
                setSelectedDistrict(e.target.value === '' ? null : Number(e.target.value))
              }
              className="w-full bg-slate-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {DISTRICT_OPTIONS.map((opt) => (
                <option key={opt.id ?? 'all'} value={opt.id ?? ''} className="bg-slate-950 text-slate-100">
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Congestion Level Filter */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">Mức độ ùn tắc</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setSelectedLevel(selectedLevel === 0 ? null : 0)}
                className={`flex items-center justify-center py-2 px-3 border rounded-lg text-xs font-semibold transition cursor-pointer ${
                  selectedLevel === 0
                    ? 'bg-green-500/20 border-green-500 text-green-400 font-bold'
                    : 'bg-slate-900/40 hover:bg-slate-900/60 border-white/10 text-slate-300'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-traffic-clear mr-2"></span>
                Thông thoáng
              </button>
              <button
                onClick={() => setSelectedLevel(selectedLevel === 1 ? null : 1)}
                className={`flex items-center justify-center py-2 px-3 border rounded-lg text-xs font-semibold transition cursor-pointer ${
                  selectedLevel === 1
                    ? 'bg-amber-500/20 border-amber-500 text-amber-400 font-bold'
                    : 'bg-slate-900/40 hover:bg-slate-900/60 border-white/10 text-slate-300'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-traffic-slow mr-2"></span>
                Chậm chạp
              </button>
              <button
                onClick={() => setSelectedLevel(selectedLevel === 2 ? null : 2)}
                className={`flex items-center justify-center py-2 px-3 border rounded-lg text-xs font-semibold col-span-2 transition cursor-pointer ${
                  selectedLevel === 2
                    ? 'bg-red-500/20 border-red-500 text-red-400 font-bold'
                    : 'bg-slate-900/40 hover:bg-slate-900/60 border-white/10 text-slate-300'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-traffic-congested mr-2"></span>
                Kẹt xe
              </button>
            </div>
          </div>

          {/* Search Input */}
          <div>
            <label className="block text-sm font-semibold text-slate-300 mb-2">Tìm kiếm tên đường</label>
            <input
              type="text"
              placeholder="Nhập tên đường..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Prediction Toggle */}
          <div className="border-t border-white/10 pt-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="block text-sm font-semibold text-slate-200">Dự báo kẹt xe (30 phút)</span>
                <span className="text-xs text-slate-400">Sử dụng AI dự đoán luồng</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={isPredictionMode}
                  onChange={(e) => setIsPredictionMode(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-500"></div>
              </label>
            </div>
          </div>
        </div>

        {/* Reset button footer */}
        <div className="p-4 border-t border-white/10 bg-slate-950/60 flex gap-2">
          <button
            onClick={handleResetFilters}
            className="flex-1 flex items-center justify-center gap-2 border border-white/10 bg-slate-900 hover:bg-slate-800 text-slate-200 py-2 rounded-lg text-sm font-medium transition cursor-pointer"
          >
            <RotateCcw size={16} />
            Reset bộ lọc
          </button>
        </div>
      </div>

      {/* 3. Floating Filter Menu Toggle Button */}
      <button
        onClick={() => setIsFilterOpen(!isFilterOpen)}
        className="absolute top-20 left-4 z-30 bg-slate-900/80 hover:bg-slate-800/80 backdrop-blur-sm border border-white/10 shadow-lg rounded-full p-3 text-slate-200 transition cursor-pointer"
      >
        <Menu size={20} />
      </button>

      {/* 4. Top-Right KPI cards overlay */}
      <div className="absolute top-20 right-4 z-30 flex flex-col gap-2 pointer-events-none">
        {/* KPI Panel */}
        <div className="flex gap-2">
          {/* Card: Red Count */}
          <div className="bg-slate-950/80 backdrop-blur-md shadow-2xl border border-white/10 rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="h-4 w-4 rounded-full bg-traffic-congested animate-pulse"></span>
            <div>
              <span className="block font-bold text-white text-sm">{redCount} điểm</span>
              <span className="block text-[10px] text-slate-400 font-medium">Đường kẹt xe</span>
            </div>
          </div>

          {/* Card: Yellow Count */}
          <div className="bg-slate-950/80 backdrop-blur-md shadow-2xl border border-white/10 rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="h-4 w-4 rounded-full bg-traffic-slow"></span>
            <div>
              <span className="block font-bold text-white text-sm">{yellowCount} điểm</span>
              <span className="block text-[10px] text-slate-400 font-medium">Đường di chuyển chậm</span>
            </div>
          </div>

          {/* Card: Avg Speed */}
          <div className="bg-slate-950/80 backdrop-blur-md shadow-2xl border border-white/10 rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="text-xl">🚗</span>
            <div>
              <span className="block font-bold text-white text-sm">{avgSpeed} km/h</span>
              <span className="block text-[10px] text-slate-400 font-medium">Tốc độ TB TP</span>
            </div>
          </div>

          {/* Card: Active Incidents */}
          {isCSGTOrAdmin && (
            <div className="bg-slate-950/80 backdrop-blur-md shadow-2xl border border-white/10 rounded-xl px-4 py-2.5 flex items-center gap-3">
              <AlertTriangle className="text-amber-500" size={18} />
              <div>
                <span className="block font-bold text-white text-sm">{activeIncidentCount}</span>
                <span className="block text-[10px] text-slate-400 font-medium">Sự cố hoạt động</span>
              </div>
            </div>
          )}
        </div>

        {/* Weather Widget */}
        {weather && (
          <div className="self-end bg-slate-950/80 backdrop-blur-md shadow-2xl border border-white/10 rounded-xl px-4 py-2.5 flex items-center gap-4 text-white">
            <div className="flex items-center gap-1">
              <Thermometer className="text-red-400" size={16} />
              <span className="text-sm font-semibold text-slate-100">{weather.temperature}°C</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-sm font-semibold text-slate-100">💧 {weather.humidity}%</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-sm font-semibold text-slate-100">💨 {weather.wind_speed} m/s</span>
            </div>
            {weather.is_raining && (
              <div className="flex items-center gap-1 text-blue-400">
                <CloudRain size={16} />
                <span className="text-xs font-semibold">Đang mưa ({weather.rain_1h_mm}mm)</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 5. Bottom Status / Auto-refresh bar */}
      <div className="absolute bottom-4 left-4 z-30 bg-slate-950/80 backdrop-blur-sm shadow-lg border border-white/10 rounded-lg px-3 py-1.5 flex items-center gap-3 text-xs text-slate-300 font-medium">
        <RefreshCw size={14} className="animate-spin text-blue-500" />
        <span>Tổng số: {totalStreets} đường | Tự động cập nhật sau {countdown} giây</span>
        <button
          onClick={() => {
            refetchTrafficState();
            setCountdown(240);
          }}
          className="hover:text-blue-400 text-blue-500 transition font-bold cursor-pointer"
        >
          Làm mới ngay
        </button>
      </div>

      {/* Prediction indicator */}
      {isPredictionMode && (
        <div className="absolute bottom-4 right-4 z-30 bg-blue-600 text-white shadow-lg rounded-lg px-4 py-2 flex items-center gap-2 text-xs font-bold animate-pulse">
          <Shield size={14} />
          <span>CHẾ ĐỘ DỰ BÁO AI KÍCH HOẠT</span>
        </div>
      )}
    </div>
  );
};

export default Home;
