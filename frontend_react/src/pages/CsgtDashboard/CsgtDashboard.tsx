import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { statsApi } from '../../api/stats.api';
import { incidentsApi } from '../../api/incidents.api';
import { useGeometry } from '../../hooks/useGeometry';
import TrafficMap from '../../components/map/TrafficMap';
import { 
  Shield, 
  Gauge, 
  AlertTriangle, 
  X, 
  Radio 
} from 'lucide-react';

const CsgtDashboard: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedStreet, setSelectedStreet] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form states
  const [incidentType, setIncidentType] = useState<'accident' | 'roadblock' | 'event' | 'community'>('accident');
  const [severity, setSeverity] = useState<number>(1);
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<'active' | 'dispatched' | 'resolved'>('dispatched');
  const [submitError, setSubmitError] = useState<string | null>(null);

  // 1. Fetch dashboard report (top congested, average speed)
  const { data: report, isLoading: isReportLoading } = useQuery({
    queryKey: ['statsReport'],
    queryFn: () => statsApi.getReport(),
    refetchInterval: 15000, // 15s auto-refresh
  });

  // 2. Load street geometry for name -> id lookup
  const { data: geometry } = useGeometry();

  // 3. Fetch active incidents for map markers
  const { data: activeIncidents } = useQuery({
    queryKey: ['activeIncidents'],
    queryFn: () => incidentsApi.getIncidents({ is_active: true }),
    refetchInterval: 10000, // 10s auto-refresh
  });

  // 4. Create Incident Mutation
  const createIncidentMutation = useMutation({
    mutationFn: (data: any) => incidentsApi.createIncident(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['activeIncidents'] });
      queryClient.invalidateQueries({ queryKey: ['statsReport'] });
      setIsModalOpen(false);
      setSelectedStreet(null);
      setDescription('');
      setSubmitError(null);
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setSubmitError(detail);
      } else if (Array.isArray(detail)) {
        const msg = detail.map((d: any) => `${d.loc.join('.')}: ${d.msg}`).join(', ');
        setSubmitError(msg);
      } else {
        setSubmitError('Không thể tạo sự cố điều phối.');
      }
    },
  });

  const handleOpenDispatch = (streetName: string) => {
    setSelectedStreet(streetName);
    setIsModalOpen(true);
    setDescription(`🚔 Điều phối lực lượng CSGT điều tiết giao thông tại khu vực đường ${streetName} do ùn tắc nghiêm trọng.`);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStreet || !geometry) return;

    // Find street ID based on name
    const streetGeom = (geometry.streets ?? []).find(
      (s) => s.street_name.toLowerCase().trim() === selectedStreet.toLowerCase().trim()
    );

    if (!streetGeom) {
      setSubmitError('Không tìm thấy ID của đường này trong cơ sở dữ liệu địa lý.');
      return;
    }

    createIncidentMutation.mutate({
      street_id: streetGeom.street_id,
      type: incidentType,
      start_time: new Date().toISOString(),
      severity,
      description,
      status,
      is_active: status !== 'resolved',
    });
  };

  // Speed Gauge Calculations (Max: 60 km/h)
  const avgSpeed = report?.avg_speed ?? 0;
  const maxGaugeSpeed = 60;
  const gaugePercent = Math.min(avgSpeed / maxGaugeSpeed, 1);
  // Semi-circle path settings (Radius = 50, center = 60,60)
  const r = 40;
  const circ = Math.PI * r; // Semi-circle circumference (approx 125.6)
  const strokeDashoffset = circ - gaugePercent * circ;

  const getGaugeColor = (speed: number) => {
    if (speed < 20) return '#ef4444'; // Red
    if (speed < 35) return '#f59e0b'; // Amber
    return '#10b981'; // Green
  };

  const getGaugeLabel = (speed: number) => {
    if (speed < 20) return 'Kẹt xe nghiêm trọng';
    if (speed < 35) return 'Giao thông di chuyển chậm';
    return 'Giao thông thông thoáng';
  };

  return (
    <div className="min-h-screen pt-20 pb-10 px-4 md:px-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b border-white/10 pb-5">
        <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
          <Shield className="text-blue-400" />
          Giao diện Điều tiết CSGT Đà Nẵng
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Hệ thống điều phối lực lượng tuần tra và xử lý kẹt xe thời gian thực dành cho cảnh sát giao thông.
        </p>
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Speed Gauge and Top Congested Streets */}
        <div className="lg:col-span-1 space-y-6">
          {/* Gauge Widget */}
          <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-6 flex flex-col items-center justify-center text-center">
            <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-1.5 self-start">
              <Gauge size={16} />
              Tốc độ toàn thành phố
            </h3>

            {/* Custom SVG Semi-circle gauge */}
            <div className="relative w-48 h-28 flex items-center justify-center overflow-hidden">
              <svg className="w-full h-full transform -rotate-180" viewBox="0 0 100 50">
                {/* Background arc */}
                <path
                  d="M 10 50 A 40 40 0 0 1 90 50"
                  fill="none"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth="8"
                  strokeLinecap="round"
                />
                {/* Value arc */}
                <path
                  d="M 10 50 A 40 40 0 0 1 90 50"
                  fill="none"
                  stroke={getGaugeColor(avgSpeed)}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={circ}
                  strokeDashoffset={strokeDashoffset}
                  className="transition-all duration-1000 ease-out"
                />
              </svg>

              {/* Central speed display text */}
              <div className="absolute bottom-0 text-center">
                <span className="text-3xl font-black text-white leading-none">
                  {Math.round(avgSpeed)}
                </span>
                <span className="text-xs text-slate-400 font-semibold block mt-0.5">km/h</span>
              </div>
            </div>

            <div className="mt-4">
              <span
                className="text-xs font-bold px-3 py-1 rounded-full border"
                style={{
                  color: getGaugeColor(avgSpeed),
                  borderColor: `${getGaugeColor(avgSpeed)}30`,
                  backgroundColor: `${getGaugeColor(avgSpeed)}08`,
                }}
              >
                {getGaugeLabel(avgSpeed)}
              </span>
            </div>
          </div>

          {/* Top Congested list with "🚔 Điều động" action button */}
          <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-6">
            <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-1.5">
              <AlertTriangle className="text-amber-500" size={16} />
              Điểm nóng ùn tắc giao thông
            </h3>

            {isReportLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-12 bg-white/5 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : report && report.top_congested && report.top_congested.length > 0 ? (
              <div className="divide-y divide-white/5 max-h-[360px] overflow-y-auto pr-1">
                {report.top_congested.map((street, idx) => (
                  <div key={`csgt-hot-${idx}`} className="py-3 flex items-center justify-between first:pt-0 last:pb-0 gap-3">
                    <div className="min-w-0">
                      <span className="text-xs font-bold text-slate-200 block truncate" title={street.street_name}>
                        {street.street_name}
                      </span>
                      <span className="text-[10px] text-slate-400 block">
                        Tốc độ TB: <b>{Math.round(street.avg_speed)} km/h</b>
                      </span>
                    </div>
                    <button
                      onClick={() => handleOpenDispatch(street.street_name)}
                      className="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold shadow-sm transition flex items-center gap-1 cursor-pointer flex-shrink-0"
                    >
                      🚔 Điều động
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-slate-400 text-xs py-10">
                Không có điểm nóng kẹt xe hiện tại.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Live Map and Dispatch Feed Info */}
        <div className="lg:col-span-2 space-y-6 flex flex-col">
          {/* Mini Real-time Map */}
          <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-4 flex flex-col flex-grow min-h-[380px]">
            <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Radio size={16} className="text-red-500 animate-pulse" />
              Bản đồ kẹt xe trực quan
            </h3>
            <div className="w-full flex-grow rounded-xl overflow-hidden border border-white/10 min-h-[300px]">
              <TrafficMap 
                activeIncidents={activeIncidents}
                onStreetClick={handleOpenDispatch}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 5. Dispatch Modal Dialog Form */}
      {isModalOpen && selectedStreet && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4">
          <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-fade-in text-white">
            {/* Modal Header */}
            <div className="bg-slate-950/60 border-b border-white/10 px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                🚔 Tạo lệnh điều động tuần tra
              </h4>
              <button
                onClick={() => {
                  setIsModalOpen(false);
                  setSelectedStreet(null);
                  setSubmitError(null);
                }}
                className="text-slate-400 hover:text-white transition cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleFormSubmit} className="p-5 space-y-4 bg-slate-900/60">
              {submitError && (
                <div className="p-2.5 bg-red-950/40 border border-red-500/30 text-red-400 rounded-lg text-xs font-semibold">
                  ⚠️ {submitError}
                </div>
              )}

              {/* Target Street */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Đường điều động
                </label>
                <input
                  type="text"
                  value={selectedStreet}
                  disabled
                  className="w-full bg-slate-950/60 text-slate-300 border border-white/10 rounded-lg px-3 py-2 text-xs font-bold cursor-not-allowed"
                />
              </div>

              {/* Incident Type & Severity */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    Loại sự cố
                  </label>
                  <select
                    value={incidentType}
                    onChange={(e: any) => setIncidentType(e.target.value)}
                    className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="accident">Tai nạn</option>
                    <option value="roadblock">Cản trở đường</option>
                    <option value="event">Sự kiện lễ hội</option>
                    <option value="community">Cộng đồng báo cáo</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    Mức độ nghiêm trọng
                  </label>
                  <select
                    value={severity}
                    onChange={(e: any) => setSeverity(Number(e.target.value))}
                    className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value={1}>Thấp (Nhẹ)</option>
                    <option value={2}>Trung bình (Chậm)</option>
                    <option value={3}>Cao (Kẹt cứng)</option>
                  </select>
                </div>
              </div>

              {/* Dispatch Action Status */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Trạng thái xử lý ban đầu
                </label>
                <select
                  value={status}
                  onChange={(e: any) => setStatus(e.target.value)}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="dispatched">🚔 Đã điều động tuần tra</option>
                  <option value="active">⚠️ Đang xảy ra sự cố</option>
                </select>
              </div>

              {/* Description */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Mô tả & Nhiệm vụ
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>

              {/* Submit Buttons */}
              <div className="pt-2 flex justify-end gap-2 border-t border-white/10 mt-4">
                <button
                  type="button"
                  onClick={() => {
                    setIsModalOpen(false);
                    setSelectedStreet(null);
                    setSubmitError(null);
                  }}
                  className="px-4 py-2 border border-white/10 rounded-lg text-xs font-semibold text-slate-400 hover:bg-white/5 transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createIncidentMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createIncidentMutation.isPending ? 'Đang gửi lệnh...' : 'Gửi lệnh đi 🚀'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CsgtDashboard;
