import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { statsApi } from '../../api/stats.api';
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
  Clock
} from 'lucide-react';

const WEEKDAYS = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ Nhật'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

const Dashboard: React.FC = () => {
  const [timeRange, setTimeRange] = useState<number>(7); // 7, 14, 30 days
  const [activeTab, setActiveTab] = useState<'trends' | 'heatmap'>('trends');

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
    queryKey: ['heatmap'],
    queryFn: () => statsApi.getHeatmap(),
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
      // API weekday is 0-indexed (0=Monday, 6=Sunday)
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

  return (
    <div className="min-h-screen bg-gray-50 pt-20 pb-10 px-4 md:px-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center gap-2">
            <span className="text-3xl">📊</span>
            Thống kê & Biểu đồ Giao thông
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Theo dõi tình trạng kẹt xe lịch sử, phân tích xu hướng giờ cao điểm và thống kê toàn thành phố.
          </p>
        </div>

        {/* Time Filter Controls */}
        <div className="flex items-center gap-2 bg-white border border-gray-200 p-1 rounded-lg shadow-sm w-fit self-end md:self-auto">
          {[7, 14, 30].map((days) => (
            <button
              key={`range-${days}`}
              onClick={() => setTimeRange(days)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition cursor-pointer ${
                timeRange === days
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              {days} ngày gần nhất
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards Grid */}
      {isReportLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-white rounded-xl border border-gray-200 animate-pulse" />
          ))}
        </div>
      ) : report ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Green Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center gap-4 hover:shadow-md transition">
            <div className="p-3 rounded-lg bg-green-50 text-green-600">
              <TrendingUp size={24} />
            </div>
            <div>
              <span className="block text-xs font-medium text-gray-500">Thông thoáng</span>
              <span className="block text-2xl font-black text-green-600 leading-none mt-1">
                {report.green_count}
              </span>
              <span className="text-[10px] text-gray-400 font-medium">Chiếm {greenPct}% mạng lưới</span>
            </div>
          </div>

          {/* Yellow Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center gap-4 hover:shadow-md transition">
            <div className="p-3 rounded-lg bg-amber-50 text-amber-500">
              <Activity size={24} />
            </div>
            <div>
              <span className="block text-xs font-medium text-gray-500">Đang chậm</span>
              <span className="block text-2xl font-black text-amber-500 leading-none mt-1">
                {report.yellow_count}
              </span>
              <span className="text-[10px] text-gray-400 font-medium">Chiếm {yellowPct}% mạng lưới</span>
            </div>
          </div>

          {/* Red Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center gap-4 hover:shadow-md transition">
            <div className="p-3 rounded-lg bg-red-50 text-red-500">
              <AlertTriangle size={24} />
            </div>
            <div>
              <span className="block text-xs font-medium text-gray-500">Kẹt xe nghiêm trọng</span>
              <span className="block text-2xl font-black text-red-500 leading-none mt-1">
                {report.red_count}
              </span>
              <span className="text-[10px] text-gray-400 font-medium">Chiếm {redPct}% mạng lưới</span>
            </div>
          </div>

          {/* Avg Speed Card */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex items-center gap-4 hover:shadow-md transition">
            <div className="p-3 rounded-lg bg-blue-50 text-blue-600">
              <Gauge size={24} />
            </div>
            <div>
              <span className="block text-xs font-medium text-gray-500">Tốc độ trung bình</span>
              <span className="block text-2xl font-black text-blue-900 leading-none mt-1">
                {Math.round(report.avg_speed)} <span className="text-sm font-medium text-gray-500">km/h</span>
              </span>
              <span className="text-[10px] text-gray-400 font-medium">Toàn thành phố Đà Nẵng</span>
            </div>
          </div>
        </div>
      ) : null}

      {/* Main Charts and Tables Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Charts Tab Container (occupies 2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
          {/* Tabs header */}
          <div className="flex border-b border-gray-200 bg-gray-50/50 p-2 justify-between items-center">
            <div className="flex gap-1">
              <button
                onClick={() => setActiveTab('trends')}
                className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition cursor-pointer ${
                  activeTab === 'trends'
                    ? 'bg-white text-blue-600 shadow-sm border border-gray-200'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                <TrendingUp size={14} />
                Xu hướng theo giờ
              </button>
              <button
                onClick={() => setActiveTab('heatmap')}
                className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition cursor-pointer ${
                  activeTab === 'heatmap'
                    ? 'bg-white text-blue-600 shadow-sm border border-gray-200'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                <Clock size={14} />
                Bản đồ nhiệt kẹt xe
              </button>
            </div>
          </div>

          {/* Chart Content Area */}
          <div className="p-6 flex-grow flex flex-col justify-center min-h-[360px]">
            {activeTab === 'trends' ? (
              isTrendLoading ? (
                <div className="h-64 flex items-center justify-center text-gray-400 animate-pulse text-sm">
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
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
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
                          backgroundColor: '#1e293b', 
                          border: 'none', 
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
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                  Không có dữ liệu xu hướng.
                </div>
              )
            ) : (
              /* Heatmap Matrix Grid Rendering */
              isHeatmapLoading ? (
                <div className="h-64 flex items-center justify-center text-gray-400 animate-pulse text-sm">
                  Đang tải bản đồ nhiệt...
                </div>
              ) : heatmapData.length > 0 ? (
                <div className="flex flex-col space-y-4">
                  <div className="overflow-x-auto pb-2">
                    <div className="min-w-[640px] flex flex-col space-y-1.5">
                      {/* Grid Header Hours */}
                      <div className="flex items-center">
                        <div className="w-16 flex-shrink-0 text-[10px] text-gray-400 font-extrabold uppercase" />
                        <div className="flex flex-1 justify-between pr-2">
                          {HOURS.map((h) => (
                            <span key={`hour-lbl-${h}`} className="w-5 text-center text-[9px] font-bold text-gray-400">
                              {h}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Heatmap Matrix Rows */}
                      {WEEKDAYS.map((dayName, dayIdx) => (
                        <div key={`day-row-${dayIdx}`} className="flex items-center">
                          <div className="w-16 flex-shrink-0 text-[10px] font-bold text-gray-600">
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
                                  {/* Custom cell tooltip */}
                                  <div className="hidden group-hover:block absolute bottom-full mb-1 bg-slate-900 text-white text-[9px] py-1 px-1.5 rounded shadow-xl whitespace-nowrap z-50 pointer-events-none">
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

                  {/* Heatmap Legend */}
                  <div className="flex items-center gap-4 text-[10px] text-gray-500 pt-2 border-t border-gray-100 justify-center">
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
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                  Không có dữ liệu bản đồ nhiệt.
                </div>
              )
            )}
          </div>
        </div>

        {/* Right Column: Top Congested Streets List (occupies 1 col) */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col overflow-hidden">
          <h3 className="text-sm font-extrabold text-gray-800 uppercase tracking-wider mb-4 flex items-center gap-1.5">
            <ShieldAlert size={16} className="text-red-500" />
            Top đường ùn tắc nhất
          </h3>

          {isReportLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-10 bg-gray-50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : report && report.top_congested && report.top_congested.length > 0 ? (
            <div className="divide-y divide-gray-100 overflow-y-auto max-h-[380px] pr-1">
              {report.top_congested.map((item, index) => (
                <div key={`congested-street-${index}`} className="py-3 flex items-center justify-between first:pt-0 last:pb-0 gap-3">
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold text-gray-400 block mb-0.5">Top #{index + 1}</span>
                    <span className="text-xs font-bold text-gray-800 block truncate" title={item.street_name}>
                      {item.street_name}
                    </span>
                    <span className="text-[10px] text-gray-400 block truncate">
                      {item.district_name || 'Đà Nẵng'}
                    </span>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-200/50 px-2 py-0.5 rounded-full block w-fit ml-auto mb-1">
                      Kẹt xe
                    </span>
                    <span className="text-[10px] font-bold text-gray-500 block">
                      TB: {Math.round(item.avg_speed)} km/h
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex-grow flex items-center justify-center text-gray-400 text-xs py-10">
              Không có dữ liệu ùn tắc hiện tại.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
