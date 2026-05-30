import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Menu, X, RotateCcw, AlertTriangle, Thermometer, CloudRain, Shield, RefreshCw } from 'lucide-react';
import TrafficMap from '../../components/map/TrafficMap';
import { trafficApi } from '../../api/traffic.api';
import { incidentsApi } from '../../api/incidents.api';
import { statsApi } from '../../api/stats.api';
import { DISTRICT_OPTIONS } from '../../constants/map.constants';

const Home: React.FC = () => {
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
        className={`absolute top-16 left-0 h-[calc(100vh-64px)] w-80 bg-white shadow-2xl transition-transform duration-300 ease-in-out z-40 flex flex-col ${
          isFilterOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-bold text-lg text-gray-800">Bộ lọc giao thông</h2>
          <button
            onClick={() => setIsFilterOpen(false)}
            className="p-1 text-gray-500 hover:text-gray-800 transition"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto space-y-6">
          {/* District Filter */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Quận/Huyện</label>
            <select
              value={selectedDistrict ?? ''}
              onChange={(e) =>
                setSelectedDistrict(e.target.value === '' ? null : Number(e.target.value))
              }
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {DISTRICT_OPTIONS.map((opt) => (
                <option key={opt.id ?? 'all'} value={opt.id ?? ''}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Congestion Level Filter */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Mức độ ùn tắc</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setSelectedLevel(selectedLevel === 0 ? null : 0)}
                className={`flex items-center justify-center py-2 px-3 border rounded-lg text-xs font-semibold transition ${
                  selectedLevel === 0
                    ? 'bg-green-50 border-green-500 text-green-700'
                    : 'bg-white hover:bg-gray-50 text-gray-700'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-traffic-clear mr-2"></span>
                Thông thoáng
              </button>
              <button
                onClick={() => setSelectedLevel(selectedLevel === 1 ? null : 1)}
                className={`flex items-center justify-center py-2 px-3 border rounded-lg text-xs font-semibold transition ${
                  selectedLevel === 1
                    ? 'bg-amber-50 border-amber-500 text-amber-700'
                    : 'bg-white hover:bg-gray-50 text-gray-700'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-traffic-slow mr-2"></span>
                Chậm chạp
              </button>
              <button
                onClick={() => setSelectedLevel(selectedLevel === 2 ? null : 2)}
                className={`flex items-center justify-center py-2 px-3 border rounded-lg text-xs font-semibold col-span-2 transition ${
                  selectedLevel === 2
                    ? 'bg-red-50 border-red-500 text-red-700'
                    : 'bg-white hover:bg-gray-50 text-gray-700'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-traffic-congested mr-2"></span>
                Kẹt xe
              </button>
            </div>
          </div>

          {/* Search Input */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Tìm kiếm tên đường</label>
            <input
              type="text"
              placeholder="Nhập tên đường..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          {/* Prediction Toggle */}
          <div className="border-t pt-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="block text-sm font-semibold text-gray-800">Dự báo kẹt xe (30 phút)</span>
                <span className="text-xs text-gray-400">Sử dụng AI dự đoán luồng</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={isPredictionMode}
                  onChange={(e) => setIsPredictionMode(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
          </div>
        </div>

        {/* Reset button footer */}
        <div className="p-4 border-t bg-gray-50 flex gap-2">
          <button
            onClick={handleResetFilters}
            className="flex-1 flex items-center justify-center gap-2 border bg-white hover:bg-gray-100 text-gray-700 py-2 rounded-lg text-sm font-medium transition"
          >
            <RotateCcw size={16} />
            Reset bộ lọc
          </button>
        </div>
      </div>

      {/* 3. Floating Filter Menu Toggle Button */}
      <button
        onClick={() => setIsFilterOpen(!isFilterOpen)}
        className="absolute top-20 left-4 z-30 bg-white hover:bg-gray-50 shadow-lg border rounded-full p-3 text-gray-700 transition"
      >
        <Menu size={20} />
      </button>

      {/* 4. Top-Right KPI cards overlay */}
      <div className="absolute top-20 right-4 z-30 flex flex-col gap-2 pointer-events-none">
        {/* KPI Panel */}
        <div className="flex gap-2">
          {/* Card: Red Count */}
          <div className="bg-white/95 backdrop-blur-sm shadow-md border rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="h-4 w-4 rounded-full bg-traffic-congested animate-pulse"></span>
            <div>
              <span className="block font-bold text-gray-800 text-sm">{redCount} điểm</span>
              <span className="block text-[10px] text-gray-400 font-medium">Đường kẹt xe</span>
            </div>
          </div>

          {/* Card: Yellow Count */}
          <div className="bg-white/95 backdrop-blur-sm shadow-md border rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="h-4 w-4 rounded-full bg-traffic-slow"></span>
            <div>
              <span className="block font-bold text-gray-800 text-sm">{yellowCount} điểm</span>
              <span className="block text-[10px] text-gray-400 font-medium">Đường di chuyển chậm</span>
            </div>
          </div>

          {/* Card: Avg Speed */}
          <div className="bg-white/95 backdrop-blur-sm shadow-md border rounded-xl px-4 py-2.5 flex items-center gap-3">
            <span className="text-xl">🚗</span>
            <div>
              <span className="block font-bold text-gray-800 text-sm">{avgSpeed} km/h</span>
              <span className="block text-[10px] text-gray-400 font-medium">Tốc độ TB TP</span>
            </div>
          </div>

          {/* Card: Active Incidents */}
          <div className="bg-white/95 backdrop-blur-sm shadow-md border rounded-xl px-4 py-2.5 flex items-center gap-3">
            <AlertTriangle className="text-amber-500" size={18} />
            <div>
              <span className="block font-bold text-gray-800 text-sm">{activeIncidentCount}</span>
              <span className="block text-[10px] text-gray-400 font-medium">Sự cố hoạt động</span>
            </div>
          </div>
        </div>

        {/* Weather Widget */}
        {weather && (
          <div className="self-end bg-white/95 backdrop-blur-sm shadow-md border rounded-xl px-4 py-2.5 flex items-center gap-4">
            <div className="flex items-center gap-1">
              <Thermometer className="text-red-500" size={16} />
              <span className="text-sm font-semibold text-gray-800">{weather.temperature}°C</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-sm font-semibold text-gray-800">💧 {weather.humidity}%</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-sm font-semibold text-gray-800">💨 {weather.wind_speed} m/s</span>
            </div>
            {weather.is_raining && (
              <div className="flex items-center gap-1 text-blue-500">
                <CloudRain size={16} />
                <span className="text-xs font-semibold">Đang mưa ({weather.rain_1h_mm}mm)</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 5. Bottom Status / Auto-refresh bar */}
      <div className="absolute bottom-4 left-4 z-30 bg-white/90 backdrop-blur-sm shadow-md border rounded-lg px-3 py-1.5 flex items-center gap-3 text-xs text-gray-500 font-medium">
        <RefreshCw size={14} className="animate-spin text-primary" />
        <span>Tổng số: {totalStreets} đường | Tự động cập nhật sau {countdown} giây</span>
        <button
          onClick={() => {
            refetchTrafficState();
            setCountdown(240);
          }}
          className="hover:text-primary transition font-bold"
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
