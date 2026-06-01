import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { statsApi } from '../../api/stats.api';
import { useAuthStore } from '../../store/authStore';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Line,
  Legend
} from 'recharts';
import { 
  Activity, 
  TrendingUp, 
  AlertTriangle, 
  ShieldAlert, 
  Gauge, 
  Clock,
  Lock,
  Search,
  Brain,
  Info,
  FileText
} from 'lucide-react';

const WEEKDAYS = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ Nhật'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

const TIMELINE_STEPS = [0, 3, 7, 14, 30];
const TIMELINE_LABELS = ['Hiện tại', '3 ngày', '7 ngày', '14 ngày', '30 ngày'];

const Dashboard: React.FC = () => {
  const [timeRange, setTimeRange] = useState<number>(0); // 0, 3, 7, 14, 30 days
  const [activeTab, setActiveTab] = useState<'trends' | 'heatmap'>('trends');
  
  // Auth state
  const { user, isLoggedIn } = useAuthStore();
  const isAuthorized = isLoggedIn && (user?.role === 'admin' || user?.role === 'csgt');

  // Queries
  const { data: report, isLoading: isReportLoading } = useQuery({
    queryKey: ['statsReport'],
    queryFn: () => statsApi.getReport(),
    refetchInterval: 30000, // 30s auto-refresh
  });

  const { data: trendData = [], isLoading: isTrendLoading } = useQuery({
    queryKey: ['hourlyTrend', timeRange],
    queryFn: () => statsApi.getHourlyTrend(timeRange),
  });

  const { data: heatmapData = [], isLoading: isHeatmapLoading } = useQuery({
    queryKey: ['heatmap', timeRange],
    queryFn: () => statsApi.getHeatmap(timeRange),
  });

  // Restricted Queries (CSGT/Admin only)
  const { data: incidentStats, isLoading: isIncidentLoading } = useQuery({
    queryKey: ['incidentStatsDashboard'],
    queryFn: () => statsApi.getIncidentStats(),
    enabled: isAuthorized,
    refetchInterval: 30000,
  });

  const { data: feedbackStats, isLoading: isFeedbackLoading } = useQuery({
    queryKey: ['feedbackStatsDashboard'],
    queryFn: () => statsApi.getFeedbackSummary(),
    enabled: isAuthorized,
    refetchInterval: 30000,
  });

  // Calculate totals for KPI percentage
  const totalStreets = report ? report.green_count + report.yellow_count + report.red_count : 0;
  const redPct = totalStreets ? Math.round((report!.red_count / totalStreets) * 100) : 0;
  const yellowPct = totalStreets ? Math.round((report!.yellow_count / totalStreets) * 100) : 0;
  const greenPct = totalStreets ? Math.round((report!.green_count / totalStreets) * 100) : 0;

  // Process Heatmap Data into 2D array matrix: weekdays (0-6) x hours (0-23)
  const buildHeatmapMatrix = () => {
    const matrix = Array.from({ length: 7 }, () => Array(24).fill(0));
    heatmapData.forEach((item) => {
      if (item.weekday >= 0 && item.weekday < 7 && item.hour >= 0 && item.hour < 24) {
        matrix[item.weekday][item.hour] = item.congestion_pct;
      }
    });
    return matrix;
  };

  const heatmapMatrix = buildHeatmapMatrix();

  const getHeatmapColor = (value: number) => {
    if (value === 0) return 'bg-slate-900 border border-slate-800/40';
    if (value <= 20) return 'bg-emerald-950/80 border border-emerald-900/20';
    if (value <= 40) return 'bg-emerald-800 border border-emerald-700/20';
    if (value <= 60) return 'bg-amber-700 border border-amber-600/20';
    if (value <= 80) return 'bg-red-800 border border-red-700/20';
    return 'bg-red-950/90 border border-red-900/50';
  };

  const sliderIndex = TIMELINE_STEPS.indexOf(timeRange) !== -1 ? TIMELINE_STEPS.indexOf(timeRange) : 2;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pt-20 pb-10 px-4 md:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-5">
          <div>
            <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
              <span className="text-3xl">📊</span>
              Thống kê & Biểu đồ Giao thông
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Phân tích xu hướng giờ cao điểm và thống kê toàn thành phố.
            </p>
          </div>

          {/* Timeline Step Slider */}
          <div className="bg-slate-900/60 border border-white/10 px-4 py-2 rounded-xl shadow-2xl flex flex-col gap-1.5 min-w-[320px]">
            <div className="flex items-center justify-between text-[11px] font-bold text-slate-400">
              <span>Mốc thời gian:</span>
              <span className={`px-2 py-0.5 rounded-md text-[9px] font-extrabold uppercase ${
                timeRange === 0 
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                  : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
              }`}>
                {timeRange === 0 ? 'Hiện tại (0h - giờ hiện tại)' : `${timeRange} ngày gần nhất`}
              </span>
            </div>
            <div className="relative mt-0.5">
              <input
                type="range"
                min="0"
                max="4"
                step="1"
                value={sliderIndex}
                onChange={(e) => {
                  const idx = parseInt(e.target.value);
                  setTimeRange(TIMELINE_STEPS[idx]);
                }}
                className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500 focus:outline-none"
              />
              <div className="flex justify-between text-[9px] text-slate-400 font-semibold mt-1 px-0.5">
                {TIMELINE_LABELS.map((lbl, idx) => (
                  <span 
                    key={`step-${idx}`}
                    className={`cursor-pointer hover:text-white transition ${timeRange === TIMELINE_STEPS[idx] ? 'text-blue-400 font-extrabold' : ''}`}
                    onClick={() => setTimeRange(TIMELINE_STEPS[idx])}
                  >
                    {lbl}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* KPI Cards Grid */}
        {isReportLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-slate-900/40 border border-white/5 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : report ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Green Card */}
            <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-xl p-4 shadow-2xl flex items-center gap-4 hover:border-white/20 transition">
              <div className="p-3 rounded-lg bg-green-500/10 text-green-400 border border-green-500/20">
                <TrendingUp size={24} />
              </div>
              <div>
                <span className="block text-xs font-medium text-slate-400">Thông thoáng</span>
                <span className="block text-2xl font-black text-green-400 leading-none mt-1">
                  {report.green_count}
                </span>
                <span className="text-[10px] text-slate-500 font-medium">Chiếm {greenPct}% mạng lưới</span>
              </div>
            </div>

            {/* Yellow Card */}
            <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-xl p-4 shadow-2xl flex items-center gap-4 hover:border-white/20 transition">
              <div className="p-3 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <Activity size={24} />
              </div>
              <div>
                <span className="block text-xs font-medium text-slate-400">Đang chậm</span>
                <span className="block text-2xl font-black text-amber-400 leading-none mt-1">
                  {report.yellow_count}
                </span>
                <span className="text-[10px] text-slate-500 font-medium">Chiếm {yellowPct}% mạng lưới</span>
              </div>
            </div>

            {/* Red Card */}
            <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-xl p-4 shadow-2xl flex items-center gap-4 hover:border-white/20 transition">
              <div className="p-3 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20">
                <AlertTriangle size={24} />
              </div>
              <div>
                <span className="block text-xs font-medium text-slate-400">Kẹt nghiêm trọng</span>
                <span className="block text-2xl font-black text-red-400 leading-none mt-1">
                  {report.red_count}
                </span>
                <span className="text-[10px] text-slate-500 font-medium">Chiếm {redPct}% mạng lưới</span>
              </div>
            </div>

            {/* Avg Speed Card */}
            <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-xl p-4 shadow-2xl flex items-center gap-4 hover:border-white/20 transition">
              <div className="p-3 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                <Gauge size={24} />
              </div>
              <div>
                <span className="block text-xs font-medium text-slate-400">Tốc độ trung bình</span>
                <span className="block text-2xl font-black text-blue-200 leading-none mt-1">
                  {Math.round(report.avg_speed)} <span className="text-sm font-medium text-slate-400">km/h</span>
                </span>
                <span className="text-[10px] text-slate-500 font-medium">Toàn mạng lưới TP. Đà Nẵng</span>
              </div>
            </div>
          </div>
        ) : null}

        {/* Main Charts and Tables Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Charts Tab Container (occupies 2 cols) */}
          <div className="lg:col-span-2 bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Tabs header */}
            <div className="flex border-b border-white/10 bg-slate-950/60 p-2 justify-between items-center">
              <div className="flex gap-1.5 w-full">
                <button
                  onClick={() => setActiveTab('trends')}
                  className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition cursor-pointer ${
                    activeTab === 'trends'
                      ? 'bg-blue-600 text-white shadow-lg'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                  }`}
                >
                  <TrendingUp size={14} />
                  Xu hướng theo giờ
                </button>
                <button
                  onClick={() => setActiveTab('heatmap')}
                  className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition cursor-pointer ${
                    activeTab === 'heatmap'
                      ? 'bg-blue-600 text-white shadow-lg'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                  }`}
                >
                  <Clock size={14} />
                  Bản đồ nhiệt kẹt xe
                </button>
              </div>
            </div>

            {/* Chart / Prediction Content Area */}
            <div className="p-6 flex-grow flex flex-col justify-center min-h-[420px]">
              
              {/* Trends Tab */}
              {activeTab === 'trends' && (
                isTrendLoading ? (
                  <div className="h-80 flex items-center justify-center text-slate-400 animate-pulse text-sm">
                    Đang tải biểu đồ xu hướng...
                  </div>
                ) : trendData.length > 0 ? (
                  <div className="w-full h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={trendData}
                        margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient id="colorCongestion" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                        <XAxis 
                          dataKey="hour" 
                          tickFormatter={(h) => `${String(h).padStart(2, '0')}:00`} 
                          stroke="#94a3b8" 
                          fontSize={10} 
                          fontWeight={600}
                        />
                        <YAxis 
                          yAxisId="left"
                          stroke="#94a3b8" 
                          fontSize={10} 
                          fontWeight={600}
                          unit="%"
                        />
                        <YAxis 
                          yAxisId="right"
                          orientation="right"
                          stroke="#94a3b8" 
                          fontSize={10} 
                          fontWeight={600}
                          unit=" km"
                        />
                        <Tooltip 
                          labelFormatter={(h) => `Thời gian: ${String(h).padStart(2, '0')}:00`}
                          contentStyle={{ 
                            backgroundColor: '#0f172a', 
                            border: '1px solid rgba(255,255,255,0.1)', 
                            borderRadius: '8px', 
                            color: '#fff',
                            fontSize: '12px'
                          }}
                        />
                        <Legend verticalAlign="top" height={36} iconType="circle" />
                        <Area 
                          yAxisId="left"
                          type="monotone" 
                          dataKey="avg_congestion_pct" 
                          name="Tỉ lệ ùn tắc (%)" 
                          stroke="#3b82f6" 
                          fillOpacity={1} 
                          fill="url(#colorCongestion)" 
                          strokeWidth={2}
                        />
                        <Line 
                          yAxisId="right"
                          type="monotone" 
                          dataKey="avg_speed" 
                          name="Tốc độ TB (km/h)" 
                          stroke="#10b981" 
                          strokeWidth={2.5}
                          dot={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-80 flex items-center justify-center text-slate-500 text-sm">
                    Không có dữ liệu xu hướng.
                  </div>
                )
              )}

              {/* Heatmap Tab */}
              {activeTab === 'heatmap' && (
                isHeatmapLoading ? (
                  <div className="h-80 flex items-center justify-center text-slate-400 animate-pulse text-sm">
                    Đang tải bản đồ nhiệt...
                  </div>
                ) : heatmapData.length > 0 ? (
                  <div className="flex flex-col space-y-4">
                    <div className="overflow-x-auto pb-2">
                      <div className="min-w-[640px] flex flex-col space-y-1.5 pt-8">
                        {/* Grid Header Hours */}
                        <div className="flex items-center">
                          <div className="w-16 flex-shrink-0 text-[10px] text-slate-500 font-extrabold uppercase" />
                          <div className="flex flex-1 justify-between pr-2">
                            {HOURS.map((h) => (
                              <span key={`hour-lbl-${h}`} className="w-5 text-center text-[9px] font-bold text-slate-400">
                                {h}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Heatmap Matrix Rows */}
                        {WEEKDAYS.map((dayName, dayIdx) => (
                          <div key={`day-row-${dayIdx}`} className="flex items-center">
                            <div className="w-16 flex-shrink-0 text-[10px] font-bold text-slate-400">
                              {dayName}
                            </div>
                            <div className="flex flex-1 gap-[2px]">
                              {HOURS.map((hour) => {
                                const value = heatmapMatrix[dayIdx][hour];
                                return (
                                  <div
                                    key={`cell-${dayIdx}-${hour}`}
                                    className={`w-5 h-5 rounded-sm transition-all hover:scale-125 cursor-pointer relative group flex items-center justify-center ${getHeatmapColor(value)}`}
                                  >
                                    {/* Custom tooltip */}
                                    <div className="hidden group-hover:block absolute left-1/2 -translate-x-1/2 bottom-full mb-1 bg-slate-900 border border-white/10 text-white text-[9px] py-1 px-1.5 rounded shadow-xl whitespace-nowrap z-50 pointer-events-none">
                                      {dayName} {hour}h: <b>{Math.round(value)}%</b> kẹt xe
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Legend */}
                    <div className="flex items-center gap-4 text-[10px] text-slate-400 pt-2 border-t border-white/5 justify-center">
                      <span className="font-bold uppercase tracking-wider">Mức kẹt:</span>
                      <div className="flex items-center gap-1.5">
                        <span className="w-3.5 h-3.5 rounded bg-slate-900 border border-slate-800" />
                        <span>Thấp (0%)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-3.5 h-3.5 rounded bg-emerald-800" />
                        <span>Bình thường</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-3.5 h-3.5 rounded bg-amber-700" />
                        <span>Đang chậm</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-3.5 h-3.5 rounded bg-red-800" />
                        <span>Nghẹt thở</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-80 flex items-center justify-center text-slate-500 text-sm">
                    Không có dữ liệu bản đồ nhiệt.
                  </div>
                )
              )}


            </div>
          </div>

          {/* Right Column: Top Congested Streets List (occupies 1 col) */}
          <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-6 flex flex-col overflow-hidden">
            <h3 className="text-sm font-extrabold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-1.5">
              <ShieldAlert size={16} className="text-red-400" />
              Top đường kẹt nhất
            </h3>

            {isReportLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-10 bg-slate-950/40 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : report && report.top_congested && report.top_congested.length > 0 ? (
              <div className="divide-y divide-white/5 overflow-y-auto custom-scrollbar max-h-[380px] pr-1">
                {report.top_congested.map((item, index) => (
                  <div key={`congested-street-${index}`} className="py-3 flex items-center justify-between first:pt-0 last:pb-0 gap-3">
                    <div className="min-w-0">
                      <span className="text-[9px] font-bold text-slate-500 block mb-0.5">HẠNG #{index + 1}</span>
                      <span className="text-xs font-bold text-slate-200 block truncate" title={item.street_name}>
                        {item.street_name}
                      </span>
                      <span className="text-[10px] text-slate-400 block truncate">
                        {item.district_name || 'Đà Nẵng'}
                      </span>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <span className="text-[9px] font-semibold text-red-400 bg-red-500/10 border border-red-500/30 px-2 py-0.5 rounded-full block w-fit ml-auto mb-1">
                        Kẹt xe
                      </span>
                      <span className="text-[10px] font-bold text-slate-400 block">
                        TB: {Math.round(item.avg_speed)} km/h
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex-grow flex items-center justify-center text-slate-500 text-xs py-10">
                Không có dữ liệu ùn tắc hiện tại.
              </div>
            )}
          </div>
        </div>

        {/* ----------------- Restricted CSGT Stats Container ----------------- */}
        <div className="border-t border-white/10 pt-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">🚨</span>
            <h2 className="text-lg font-bold text-white">Thống kê Sự cố & Phản ánh (CSGT & Admin)</h2>
          </div>

          <div className="relative">
            {/* Lock Guard Overlay for Guest Users */}
            {!isAuthorized && (
              <div className="absolute inset-0 z-20 bg-slate-950/80 backdrop-blur-md rounded-2xl flex flex-col items-center justify-center text-center p-6 border border-white/10 shadow-2xl">
                <div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-3 shadow-lg">
                  <Lock size={20} />
                </div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Giới Hạn Quyền Truy Cập</h3>
                <p className="text-xs text-slate-400 max-w-md mt-1.5 mb-4">
                  Thống kê sự cố giao thông, các đoạn cấm đường và phản ánh trực tiếp từ người dân chỉ dành cho cán bộ CSGT hoặc Quản trị viên. Vui lòng đăng nhập để truy cập dữ liệu này.
                </p>
                <Link 
                  to="/login"
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-5 py-2 rounded-lg shadow-md transition hover:scale-105 duration-200 cursor-pointer"
                >
                  Đăng nhập tài khoản điều hành
                </Link>
              </div>
            )}

            {/* The Actual Restricted Content Block */}
            <div className={`grid grid-cols-1 lg:grid-cols-2 gap-6 ${!isAuthorized ? 'filter blur-sm select-none opacity-40 pointer-events-none' : ''}`}>
              
              {/* Incident Stats Card */}
              <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-6 flex flex-col justify-between min-h-[280px]">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <FileText size={16} className="text-blue-400" />
                    Thống kê Sự cố & Lô cốt đang hoạt động
                  </h3>
                  
                  {isIncidentLoading ? (
                    <div className="space-y-4 animate-pulse">
                      <div className="h-6 bg-slate-950 rounded w-1/3" />
                      <div className="h-20 bg-slate-950 rounded" />
                    </div>
                  ) : incidentStats ? (
                    <div className="space-y-4">
                      {/* Sub-KPIs */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-950/60 border border-white/5 rounded-xl p-3">
                          <span className="text-[10px] text-slate-500 font-bold block uppercase">Đang xảy ra</span>
                          <span className="text-2xl font-black text-blue-400 block mt-1">{incidentStats.total_active} <span className="text-xs font-normal text-slate-400">sự cố</span></span>
                        </div>
                        <div className="bg-slate-950/60 border border-white/5 rounded-xl p-3">
                          <span className="text-[10px] text-slate-500 font-bold block uppercase">Xử lý trung bình</span>
                          <span className="text-2xl font-black text-emerald-400 block mt-1">{incidentStats.avg_resolve_time_minutes} <span className="text-xs font-normal text-slate-400">phút</span></span>
                        </div>
                      </div>

                      {/* Type breakdowns */}
                      <div className="space-y-2">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Phân loại sự cố:</span>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="flex justify-between items-center bg-slate-950/30 p-2 rounded border border-white/5 text-[11px]">
                            <span className="text-slate-400">🚧 Rào chắn/Lô cốt</span>
                            <span className="font-bold text-slate-200">{incidentStats.by_type?.roadblock || 0}</span>
                          </div>
                          <div className="flex justify-between items-center bg-slate-950/30 p-2 rounded border border-white/5 text-[11px]">
                            <span className="text-slate-400">🚨 Tai nạn</span>
                            <span className="font-bold text-slate-200">{incidentStats.by_type?.accident || 0}</span>
                          </div>
                          <div className="flex justify-between items-center bg-slate-950/30 p-2 rounded border border-white/5 text-[11px]">
                            <span className="text-slate-400">📅 Sự kiện đông người</span>
                            <span className="font-bold text-slate-200">{incidentStats.by_type?.event || 0}</span>
                          </div>
                          <div className="flex justify-between items-center bg-slate-950/30 p-2 rounded border border-white/5 text-[11px]">
                            <span className="text-slate-400">👥 Cộng đồng báo</span>
                            <span className="font-bold text-slate-200">{incidentStats.by_type?.community || 0}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 text-xs py-10">Không có dữ liệu sự cố.</div>
                  )}
                </div>

                {/* Bottom Severity indicators */}
                {incidentStats && (
                  <div className="flex items-center gap-4 text-[10px] text-slate-500 mt-4 pt-3 border-t border-white/5 justify-between">
                    <span className="font-bold uppercase">Mức độ nghiêm trọng:</span>
                    <div className="flex gap-2">
                      <span className="bg-green-500/10 text-green-400 px-2 py-0.5 rounded border border-green-500/25">
                        Thấp: {incidentStats.by_severity?.[1] || 0}
                      </span>
                      <span className="bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded border border-amber-500/25">
                        Trung bình: {incidentStats.by_severity?.[2] || 0}
                      </span>
                      <span className="bg-red-500/10 text-red-400 px-2 py-0.5 rounded border border-red-500/25">
                        Cao: {incidentStats.by_severity?.[3] || 0}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Feedback Summary Card */}
              <div className="bg-slate-900/50 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-6 flex flex-col justify-between min-h-[280px]">
                <div>
                  <h3 className="text-sm font-extrabold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Activity size={16} className="text-emerald-400" />
                    Phản ánh người dân (24 giờ qua)
                  </h3>

                  {isFeedbackLoading ? (
                    <div className="space-y-4 animate-pulse">
                      <div className="h-6 bg-slate-950 rounded w-1/3" />
                      <div className="h-20 bg-slate-950 rounded" />
                    </div>
                  ) : feedbackStats ? (
                    <div className="space-y-3">
                      {/* Sub-KPIs */}
                      <div className="bg-slate-950/60 border border-white/5 rounded-xl p-3 flex justify-between items-center">
                        <div>
                          <span className="text-[10px] text-slate-500 font-bold block uppercase">Tổng số phản ánh gửi lên</span>
                          <span className="text-2xl font-black text-emerald-400 block mt-1">
                            {feedbackStats.total_reports} <span className="text-xs font-normal text-slate-400">báo cáo</span>
                          </span>
                        </div>
                        {/* Tiny breakdown badges */}
                        <div className="flex flex-col gap-1 text-[9px]">
                          <span className="text-red-400 font-bold bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded">
                            Kẹt xe: {feedbackStats.by_type?.congested || 0}
                          </span>
                          <span className="text-green-400 font-bold bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded">
                            Thông thoáng: {feedbackStats.by_type?.clear || 0}
                          </span>
                        </div>
                      </div>

                      {/* Top reported streets list */}
                      <div className="space-y-2">
                        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Các tuyến đường bị báo cáo nhiều nhất:</span>
                        <div className="space-y-1">
                          {feedbackStats.top_reported_streets?.length > 0 ? (
                            feedbackStats.top_reported_streets.map((st, sIdx) => (
                              <div key={`rep-st-${sIdx}`} className="flex justify-between items-center text-xs py-1 border-b border-white/5 last:border-b-0">
                                <span className="font-semibold text-slate-300">{st.street_name}</span>
                                <span className="text-[10px] font-extrabold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
                                  {st.report_count} lượt flag
                                </span>
                              </div>
                            ))
                          ) : (
                            <p className="text-[10px] text-slate-500 italic">Chưa ghi nhận phản ánh kẹt xe nào.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 text-xs py-10">Không có dữ liệu phản ánh.</div>
                  )}
                </div>
                
                {/* Info footer */}
                <div className="flex items-center gap-1.5 text-[9px] text-slate-500 pt-3 border-t border-white/5 mt-3">
                  <Info size={10} />
                  <span>Dữ liệu này được làm mới tự động nhằm phục vụ điều tiết giao thông thời gian thực.</span>
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-slate-600 text-xs pt-10 border-t border-white/5">
          📊 Command Dashboard · PBL5 Hệ thống Giám sát Giao thông Đà Nẵng · v1.3
        </div>

      </div>
    </div>
  );
};

export default Dashboard;
