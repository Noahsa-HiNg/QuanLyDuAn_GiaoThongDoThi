import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { statsApi } from '../../api/stats.api';
import { incidentsApi } from '../../api/incidents.api';
import { usersApi } from '../../api/users.api';
import { useGeometry } from '../../hooks/useGeometry';
import TrafficMap from '../../components/map/TrafficMap';
import { communityApi } from '../../api/community.api';
import { emergencyApi } from '../../api/emergency.api';
import { auditApi } from '../../api/audit.api';
import api from '../../lib/axios';
import { 
  Shield, 
  Gauge, 
  AlertTriangle, 
  X, 
  Radio,
  Users,
  Megaphone,
  ClipboardList,
  CheckCircle
} from 'lucide-react';
const getDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * (Math.PI / 180);
  const dLon = (lon2 - lon1) * (Math.PI / 180);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * (Math.PI / 180)) * Math.cos(lat2 * (Math.PI / 180)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

const CsgtDashboard: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'dispatch' | 'community' | 'emergency' | 'audit'>('dispatch');
  const [selectedStreet, setSelectedStreet] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [clickCoords, setClickCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [selectedOfficerId, setSelectedOfficerId] = useState<number | null>(null);
  const [editingIncidentId, setEditingIncidentId] = useState<number | null>(null);
  const [mapFlyToCoords, setMapFlyToCoords] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    const handleFlyTo = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail && customEvent.detail.lat && customEvent.detail.lng) {
        setMapFlyToCoords({ lat: customEvent.detail.lat, lng: customEvent.detail.lng });
        setActiveTab('dispatch');
      }
    };
    window.addEventListener('map-fly-to', handleFlyTo);
    return () => window.removeEventListener('map-fly-to', handleFlyTo);
  }, []);

  // Emergency banner states
  const [bannerTitle, setBannerTitle] = useState('');
  const [bannerContent, setBannerContent] = useState('');
  const [bannerExpiresIn, setBannerExpiresIn] = useState<number>(2); // in hours

  // Custom alert modal state
  const [customAlert, setCustomAlert] = useState<{ isOpen: boolean; title: string; message: string; type?: 'info' | 'success' | 'error' }>({
    isOpen: false,
    title: '',
    message: '',
  });

  const showAlert = (title: string, message: string, type: 'info' | 'success' | 'error' = 'info') => {
    setCustomAlert({ isOpen: true, title, message, type });
  };

  // Queries for tabs
  const { data: communityReportsHistory = [], isLoading: communityReportsLoading } = useQuery({
    queryKey: ['communityReportsHistory'],
    queryFn: () => communityApi.getReports(),
    refetchInterval: 15000,
    enabled: true,
  });

  const { data: auditLogs = [], isLoading: auditLogsLoading } = useQuery({
    queryKey: ['auditLogs'],
    queryFn: () => auditApi.getLogs(50),
    refetchInterval: 30000,
    enabled: activeTab === 'audit',
  });

  // Mutations
  const verifyReportMutation = useMutation({
    mutationFn: (id: number) => api.post(`/api/community/report/${id}/verify`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['communityReportsHistory'] });
      queryClient.invalidateQueries({ queryKey: ['activeIncidents'] });
      showAlert('Xác minh thành công', 'Đã xác minh và lưu nhận phản ánh kẹt xe của người dân thành công!', 'success');
    },
    onError: (err: any) => {
      showAlert('Thất bại', `Xác minh thất bại: ${err.response?.data?.detail || err.message}`, 'error');
    }
  });
  const verifyReportsBatchMutation = useMutation({
    mutationFn: (ids: number[]) => api.post('/api/community/reports/verify-batch', ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['communityReportsHistory'] });
      queryClient.invalidateQueries({ queryKey: ['activeIncidents'] });
    },
    onError: (err: any) => {
      showAlert('Thất bại', `Xác minh cụm thất bại: ${err.response?.data?.detail || err.message}`, 'error');
    }
  });

  const handleVerifyReport = (id: number) => {
    verifyReportMutation.mutate(id, {
      onSuccess: () => {
        const report = communityReportsHistory.find((r: any) => r.id === id);
        if (report) {
          let streetName = '';
          if (geometry?.streets) {
            let minDistance = Infinity;
            geometry.streets.forEach((s: any) => {
              if (!s.path || s.path.length === 0) return;
              s.path.forEach((pt: any) => {
                const dist = getDistance(report.latitude, report.longitude, pt[1], pt[0]);
                if (dist < minDistance) {
                  minDistance = dist;
                  streetName = s.street_name;
                }
              });
            });
          }
          if (streetName) {
            setSelectedStreet(streetName);
            setIncidentType('community');
            setSeverity(2);
            setDescription(`Tuần tra điều phối kẹt xe tại đường ${streetName} được báo cáo từ người dân.`);
            setClickCoords({ lat: report.latitude, lng: report.longitude });
            setIsModalOpen(true);
            showAlert('Xác minh thành công', `Đã xác minh báo cáo kẹt xe trên đường ${streetName}. Hãy hoàn tất điều động lực lượng tuần tra!`, 'success');
          } else {
            showAlert('Xác minh thành công', 'Đã xác minh và lưu nhận phản ánh kẹt xe của người dân thành công!', 'success');
          }
        }
      }
    });
  };

  const handleVerifyCluster = (ids: number[]) => {
    verifyReportsBatchMutation.mutate(ids, {
      onSuccess: () => {
        const firstReport = communityReportsHistory.find((r: any) => ids.includes(r.id));
        if (firstReport) {
          let streetName = '';
          if (geometry?.streets) {
            let minDistance = Infinity;
            geometry.streets.forEach((s: any) => {
              if (!s.path || s.path.length === 0) return;
              s.path.forEach((pt: any) => {
                const dist = getDistance(firstReport.latitude, firstReport.longitude, pt[1], pt[0]);
                if (dist < minDistance) {
                  minDistance = dist;
                  streetName = s.street_name;
                }
              });
            });
          }
          if (streetName) {
            setSelectedStreet(streetName);
            setIncidentType('community');
            setSeverity(2);
            setDescription(`Tuần tra điều phối cụm kẹt xe tại đường ${streetName} được báo cáo từ người dân.`);
            setClickCoords({ lat: firstReport.latitude, lng: firstReport.longitude });
            setIsModalOpen(true);
            showAlert('Xác minh thành công', `Đã xác minh cụm kẹt xe trên đường ${streetName}. Hãy hoàn tất điều động lực lượng tuần tra!`, 'success');
          } else {
            showAlert('Xác minh thành công', 'Đã xác minh cụm báo cáo kẹt xe thành công!', 'success');
          }
        }
      }
    });
  };

  const bannerMutation = useMutation({
    mutationFn: (data: { title: string; content: string; expires_at?: string }) => 
      emergencyApi.createAlert(data.title, data.content, data.expires_at),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emergencyAlerts'] });
      queryClient.invalidateQueries({ queryKey: ['active-alert'] });
      showAlert('Phát thông báo', 'Đã phát thông báo khẩn cấp toàn hệ thống thành công!', 'success');
      setBannerTitle('');
      setBannerContent('');
    },
    onError: (err: any) => {
      showAlert('Thất bại', `Không thể phát thông báo: ${err.response?.data?.detail || err.message}`, 'error');
    }
  });

  // Query to fetch emergency alerts list
  const { data: emergencyAlerts = [], isLoading: alertsLoading } = useQuery({
    queryKey: ['emergencyAlerts'],
    queryFn: () => emergencyApi.getAlertList(),
    refetchInterval: 15000,
    enabled: activeTab === 'emergency',
  });

  // Mutation to deactivate an alert
  const deactivateAlertMutation = useMutation({
    mutationFn: (id: number) => emergencyApi.deactivateAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emergencyAlerts'] });
      queryClient.invalidateQueries({ queryKey: ['active-alert'] });
      showAlert('Hủy thông báo', 'Đã hủy thông báo khẩn cấp thành công!', 'success');
    },
    onError: (err: any) => {
      showAlert('Thất bại', `Hủy thông báo thất bại: ${err.response?.data?.detail || err.message}`, 'error');
    }
  });

  const handleCreateBanner = (e: React.FormEvent) => {
    e.preventDefault();
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + bannerExpiresIn);
    bannerMutation.mutate({
      title: bannerTitle,
      content: bannerContent,
      expires_at: expiresAt.toISOString()
    });
  };

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

  // Fetch active CSGT officers
  const { data: officers = [] } = useQuery({
    queryKey: ['activeOfficers'],
    queryFn: () => usersApi.getOfficers(),
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
      setClickCoords(null);
      setSelectedOfficerId(null);
      setDescription('');
      setEditingIncidentId(null);
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

  // 4b. Update Incident Mutation (for re-dispatch)
  const updateIncidentMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => incidentsApi.updateIncident(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['activeIncidents'] });
      queryClient.invalidateQueries({ queryKey: ['statsReport'] });
      setIsModalOpen(false);
      setSelectedStreet(null);
      setClickCoords(null);
      setSelectedOfficerId(null);
      setDescription('');
      setEditingIncidentId(null);
      setSubmitError(null);
      showAlert('Thành công', 'Đã cập nhật lệnh điều động lại thành công!', 'success');
    },
    onError: (err: any) => {
      setSubmitError(err.response?.data?.detail || 'Không thể cập nhật lệnh điều phối.');
    },
  });

  // 4c. Delete Incident Mutation (for skipping declined dispatches)
  const deleteIncidentMutation = useMutation({
    mutationFn: (id: number) => incidentsApi.deleteIncident(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['activeIncidents'] });
      queryClient.invalidateQueries({ queryKey: ['statsReport'] });
      showAlert('Đã xóa', 'Đã hủy bỏ sự cố khỏi bản đồ thành công.', 'info');
    },
    onError: (err: any) => {
      showAlert('Thất bại', `Không thể xóa sự cố: ${err.response?.data?.detail || err.message}`, 'error');
    },
  });

  const handleOpenDispatch = (streetName: string, coords?: { lat: number; lng: number }) => {
    setSelectedStreet(streetName);
    setClickCoords(coords || null);
    setIsModalOpen(true);
    setDescription(`🚔 Điều phối lực lượng CSGT điều tiết giao thông tại khu vực đường ${streetName} do ùn tắc nghiêm trọng.`);
    setSelectedOfficerId(null);
    setEditingIncidentId(null);
  };

  const handleOpenRedispatch = (incident: any) => {
    const streetGeom = (geometry?.streets ?? []).find((s) => s.street_id === incident.street_id);
    setSelectedStreet(streetGeom ? streetGeom.street_name : 'Không rõ');
    setIncidentType(incident.type);
    setSeverity(incident.severity);
    setDescription(incident.description || '');
    setStatus('dispatched');
    setSelectedOfficerId(null);
    setClickCoords({ lat: incident.latitude, lng: incident.longitude });
    setEditingIncidentId(incident.id);
    setIsModalOpen(true);
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

    const payload = {
      street_id: streetGeom.street_id,
      type: incidentType,
      severity,
      description,
      status,
      is_active: status !== 'resolved',
      latitude: clickCoords?.lat ?? null,
      longitude: clickCoords?.lng ?? null,
      officer_id: selectedOfficerId,
    };

    if (editingIncidentId !== null) {
      updateIncidentMutation.mutate({
        id: editingIncidentId,
        data: payload
      });
    } else {
      createIncidentMutation.mutate({
        ...payload,
        start_time: new Date().toISOString(),
      });
    }
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

      {/* Tab Switcher Headers (S5-53, S5-54, S5-57) */}
      <div className="flex border-b border-white/10 gap-6 text-sm font-bold text-slate-400 overflow-x-auto pb-1.5 scrollbar-thin">
        <button
          onClick={() => setActiveTab('dispatch')}
          className={`pb-3 relative cursor-pointer whitespace-nowrap flex items-center gap-1.5 transition ${
            activeTab === 'dispatch' ? 'text-white border-b-2 border-blue-500 font-extrabold' : 'hover:text-white'
          }`}
        >
          <Radio size={16} />
          Điều phối chính
        </button>
        <button
          onClick={() => setActiveTab('community')}
          className={`pb-3 relative cursor-pointer whitespace-nowrap flex items-center gap-1.5 transition ${
            activeTab === 'community' ? 'text-white border-b-2 border-blue-500 font-extrabold' : 'hover:text-white'
          }`}
        >
          <Users size={16} />
          Báo cáo Cộng đồng
        </button>
        <button
          onClick={() => setActiveTab('emergency')}
          className={`pb-3 relative cursor-pointer whitespace-nowrap flex items-center gap-1.5 transition ${
            activeTab === 'emergency' ? 'text-white border-b-2 border-blue-500 font-extrabold' : 'hover:text-white'
          }`}
        >
          <Megaphone size={16} />
          Loa thông báo khẩn
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`pb-3 relative cursor-pointer whitespace-nowrap flex items-center gap-1.5 transition ${
            activeTab === 'audit' ? 'text-white border-b-2 border-blue-500 font-extrabold' : 'hover:text-white'
          }`}
        >
          <ClipboardList size={16} />
          Nhật ký hệ thống
        </button>
      </div>

      {/* Tab 1: Dispatch Control Center */}
      {activeTab === 'dispatch' && (
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
              <div className="divide-y divide-white/5 max-h-[360px] overflow-y-auto custom-scrollbar pr-1">
                {report.top_congested.map((street, idx) => (
                  <div key={`csgt-hot-${idx}`} className="py-3 flex items-center justify-between first:pt-0 last:pb-0 gap-3">
                    <div className="min-w-0">
                      <span
                        onClick={() => {
                          const streetGeom = (geometry?.streets ?? []).find(
                            (s: any) => s.street_name.toLowerCase().trim() === street.street_name.toLowerCase().trim()
                          );
                          if (streetGeom && streetGeom.path && streetGeom.path.length > 0) {
                            const midIdx = Math.floor(streetGeom.path.length / 2);
                            const pt = streetGeom.path[midIdx];
                            setMapFlyToCoords({ lat: pt[1], lng: pt[0] });
                          }
                        }}
                        className="text-xs font-bold text-slate-200 block truncate cursor-pointer hover:text-blue-400 hover:underline"
                        title={street.street_name}
                      >
                        {street.street_name}
                      </span>
                      <span className="text-[10px] text-slate-400 block">
                        Tốc độ TB: <b>{Math.round(street.avg_speed)} km/h</b>
                      </span>
                    </div>
                    <button
                      onClick={() => handleOpenDispatch(street.street_name)}
                      className="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold shadow-sm transition flex items-center gap-1 cursor-pointer flex-shrink-0 border-0"
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

          {/* Declined Incidents Widget */}
          {activeIncidents && activeIncidents.some((inc) => inc.status === 'declined') && (
            <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-red-500/20 shadow-2xl p-6">
              <h3 className="text-xs font-extrabold text-red-400 uppercase tracking-wider mb-4 flex items-center gap-1.5">
                <AlertTriangle className="text-red-500 animate-pulse" size={16} />
                Lệnh điều động bị từ chối
              </h3>
              <div className="divide-y divide-white/5 max-h-[300px] overflow-y-auto custom-scrollbar pr-1">
                {activeIncidents
                  .filter((inc) => inc.status === 'declined')
                  .map((inc) => {
                    const streetGeom = (geometry?.streets ?? []).find((s) => s.street_id === inc.street_id);
                    const officer = officers.find((o: any) => o.id === inc.officer_id);
                    return (
                      <div key={`declined-inc-${inc.id}`} className="py-3 flex flex-col gap-2 first:pt-0 last:pb-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <span className="text-xs font-bold text-red-300 block">
                              📍 {streetGeom ? streetGeom.street_name : 'Không rõ'}
                            </span>
                            <span className="text-[10px] text-slate-400 block mt-0.5">
                              CSGT từ chối: <b className="text-slate-300">{officer ? officer.full_name : 'Chưa rõ'}</b>
                            </span>
                            <p className="text-[10px] text-slate-400 mt-1 italic line-clamp-2" title={inc.description || ''}>
                              "{inc.description}"
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => deleteIncidentMutation.mutate(inc.id)}
                            disabled={deleteIncidentMutation.isPending}
                            className="px-2.5 py-1.5 border border-white/10 hover:bg-white/5 text-slate-300 rounded-lg text-[10px] font-bold shadow-sm transition cursor-pointer"
                          >
                            Bỏ qua
                          </button>
                          <button
                            onClick={() => handleOpenRedispatch(inc)}
                            className="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold shadow-sm transition cursor-pointer"
                          >
                            Điều động lại
                          </button>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
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
                communityReports={communityReportsHistory}
                showCommunityReports={true}
                isCsgtView={true}
                onVerifyReport={handleVerifyReport}
                onVerifyCluster={handleVerifyCluster}
                flyToCoords={mapFlyToCoords}
                pageContext="csgt"
              />
            </div>
          </div>
        </div>
      </div>
    )}

      {/* 5. Dispatch Modal Dialog Form */}
      {isModalOpen && selectedStreet && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4">
          <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-fade-in text-white">
            {/* Modal Header */}
            <div className="bg-slate-950/60 border-b border-white/10 px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                {editingIncidentId !== null ? '🚔 Điều động lại lực lượng CSGT' : '🚔 Tạo lệnh điều động tuần tra'}
              </h4>
              <button
                onClick={() => {
                  setIsModalOpen(false);
                  setSelectedStreet(null);
                  setEditingIncidentId(null);
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

              {/* Officer assignment select */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Chiến sĩ được phân công
                </label>
                <select
                  value={selectedOfficerId || ''}
                  onChange={(e: any) => setSelectedOfficerId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="">-- Chưa phân công --</option>
                  {officers.map((off: any) => {
                    const busy = off.is_busy || (activeIncidents ?? []).some(
                      (inc) => inc.officer_id === off.id && inc.status !== 'resolved'
                    );
                    return (
                      <option key={off.id} value={off.id}>
                        {off.full_name} ({off.email}) {busy ? '🔴 [Đang bận]' : '🟢 [Sẵn sàng]'}
                      </option>
                    );
                  })}
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
                    setEditingIncidentId(null);
                    setSubmitError(null);
                  }}
                  className="px-4 py-2 border border-white/10 rounded-lg text-xs font-semibold text-slate-400 hover:bg-white/5 transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createIncidentMutation.isPending || updateIncidentMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createIncidentMutation.isPending || updateIncidentMutation.isPending
                    ? 'Đang gửi...'
                    : editingIncidentId !== null
                      ? 'Cập nhật & Gửi lệnh 🚀'
                      : 'Gửi lệnh đi 🚀'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Tab 2: Báo cáo Cộng đồng */}
      {activeTab === 'community' && (
        <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Users className="text-amber-500" size={20} />
                Báo cáo kẹt xe từ người dân (Cộng đồng)
              </h3>
              <p className="text-xs text-slate-400">Danh sách các phản ánh ùn tắc từ người dân gửi lên hệ thống.</p>
            </div>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['communityReportsHistory'] })}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
            >
              Làm mới
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-slate-400 font-extrabold uppercase tracking-wider">
                  <th className="py-3 px-4">Mã số</th>
                  <th className="py-3 px-4">Tọa độ</th>
                  <th className="py-3 px-4">Mức độ kẹt</th>
                  <th className="py-3 px-4">Mô tả chi tiết</th>
                  <th className="py-3 px-4">Thời gian gửi</th>
                  <th className="py-3 px-4">Xác minh</th>
                  <th className="py-3 px-4 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {communityReportsLoading ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400">Đang tải dữ liệu...</td>
                  </tr>
                ) : !communityReportsHistory || communityReportsHistory.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400">Không có báo cáo kẹt xe nào từ cộng đồng.</td>
                  </tr>
                ) : (
                  communityReportsHistory.map((report: any) => (
                    <tr key={report.id} className="hover:bg-white/5 transition">
                      <td className="py-3 px-4 font-mono font-bold text-slate-300">#{report.id}</td>
                      <td className="py-3 px-4 font-mono text-slate-400">
                        {report.latitude.toFixed(6)}, {report.longitude.toFixed(6)}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          report.severity === 3 
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30' 
                            : report.severity === 2
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              : 'bg-green-500/20 text-green-400 border border-green-500/30'
                        }`}>
                          {report.severity === 3 ? '🔴 Nặng (Kẹt cứng)' : report.severity === 2 ? '🟡 Vừa (Ùn ứ)' : '🟢 Nhẹ (Chậm)'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-300 max-w-[200px] truncate" title={report.description}>
                        {report.description || 'Không có mô tả chi tiết.'}
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {new Date(report.reported_at).toLocaleString('vi-VN')}
                      </td>
                      <td className="py-3 px-4">
                        {report.is_verified ? (
                          <span className="text-green-400 font-bold flex items-center gap-1">
                            <CheckCircle size={14} /> Đã duyệt
                          </span>
                        ) : (
                          <span className="text-slate-500">Chưa duyệt</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {!report.is_verified ? (
                          <button
                            onClick={() => handleVerifyReport(report.id)}
                            disabled={verifyReportMutation.isPending}
                            className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-[11px] font-bold transition cursor-pointer disabled:opacity-50 border-0"
                          >
                            {verifyReportMutation.isPending ? 'Đang duyệt...' : '✅ Duyệt kẹt'}
                          </button>
                        ) : (
                          <span className="text-[11px] text-slate-500 font-semibold">-</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Loa thông báo khẩn */}
      {activeTab === 'emergency' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Cài đặt thông báo */}
          <div className="lg:col-span-4 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-6 space-y-6">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Megaphone className="text-rose-500" size={20} />
                Cài đặt Loa thông báo khẩn cấp (Toàn thành phố)
              </h3>
              <p className="text-xs text-slate-400">Phát tin cảnh báo khẩn cấp nổi bật hiển thị ở toàn bộ trang chủ của người dân.</p>
            </div>

            <form onSubmit={handleCreateBanner} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Tiêu đề cảnh báo</label>
                <input
                  type="text"
                  value={bannerTitle}
                  onChange={(e) => setBannerTitle(e.target.value)}
                  placeholder="Ví dụ: 🚨 CẤM ĐƯỜNG PHỤC VỤ SỰ KIỆN PHÁO HOA QUỐC TẾ hoặc BÃO LỚN"
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-rose-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Nội dung chi tiết</label>
                <textarea
                  value={bannerContent}
                  onChange={(e) => setBannerContent(e.target.value)}
                  placeholder="Ví dụ: Bắt đầu từ 19h00 hôm nay, cấm toàn bộ phương tiện lưu thông qua cầu Rồng và cầu Trần Thị Lý..."
                  rows={4}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-rose-500 resize-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Thời gian tự động ẩn</label>
                <select
                  value={bannerExpiresIn}
                  onChange={(e) => setBannerExpiresIn(Number(e.target.value))}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-rose-500 cursor-pointer"
                >
                  <option value={1}>1 giờ</option>
                  <option value={2}>2 giờ</option>
                  <option value={6}>6 giờ</option>
                  <option value={12}>12 giờ</option>
                  <option value={24}>24 giờ</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={bannerMutation.isPending}
                className="w-full py-2.5 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white rounded-lg text-xs font-bold shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {bannerMutation.isPending ? 'Đang phát sóng...' : '📢 Kích hoạt cảnh báo khẩn cấp'}
              </button>
            </form>
          </div>

          {/* Lịch sử và trạng thái */}
          <div className="lg:col-span-8 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-6 space-y-4">
            <div className="border-b border-white/10 pb-4">
              <h3 className="text-lg font-bold text-white">Lịch sử phát thông báo</h3>
              <p className="text-xs text-slate-400">Danh sách các thông báo đã và đang hoạt động. CSGT có thể hủy phát sóng thông báo bất kỳ lúc nào.</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-extrabold uppercase tracking-wider">
                    <th className="py-3 px-4">Mã</th>
                    <th className="py-3 px-4">Tiêu đề & Nội dung</th>
                    <th className="py-3 px-4">Thời gian phát</th>
                    <th className="py-3 px-4">Hạn dùng</th>
                    <th className="py-3 px-4">Trạng thái</th>
                    <th className="py-3 px-4 text-center">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-slate-300">
                  {alertsLoading ? (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-slate-400">Đang tải dữ liệu...</td>
                    </tr>
                  ) : !emergencyAlerts || emergencyAlerts.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-slate-400">Chưa có thông báo nào được phát.</td>
                    </tr>
                  ) : (
                    emergencyAlerts.map((alert: any) => {
                      const now = new Date();
                      const expired = alert.expires_at ? new Date(alert.expires_at) < now : false;
                      const isActive = alert.is_active && !expired;
                      return (
                        <tr key={alert.id} className="hover:bg-white/5 transition text-slate-300">
                          <td className="py-3 px-4 font-mono font-bold">#{alert.id}</td>
                          <td className="py-3 px-4 max-w-xs">
                            <strong className="block text-white text-xs">{alert.title}</strong>
                            <span className="text-[10px] text-slate-400 block truncate" title={alert.content}>
                              {alert.content}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-400">
                            {new Date(alert.created_at).toLocaleString('vi-VN')}
                          </td>
                          <td className="py-3 px-4 text-slate-400">
                            {alert.expires_at ? new Date(alert.expires_at).toLocaleString('vi-VN') : 'Không thời hạn'}
                          </td>
                          <td className="py-3 px-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              isActive
                                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                : alert.is_active === false
                                  ? 'bg-slate-500/20 text-slate-400 border border-white/10'
                                  : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            }`}>
                              {isActive ? '🔴 Đang phát' : alert.is_active === false ? '⚪ Đã hủy' : '🟡 Hết hạn'}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            {isActive ? (
                              <button
                                onClick={() => deactivateAlertMutation.mutate(alert.id)}
                                disabled={deactivateAlertMutation.isPending}
                                className="px-2.5 py-1 bg-red-600 hover:bg-red-500 text-white rounded text-[10px] font-bold transition cursor-pointer disabled:opacity-50 border-0"
                              >
                                {deactivateAlertMutation.isPending ? 'Đang hủy...' : '🛑 Hủy phát'}
                              </button>
                            ) : (
                              <span className="text-[10px] text-slate-500 font-semibold">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Nhật ký hệ thống */}
      {activeTab === 'audit' && (
        <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <ClipboardList className="text-blue-500" size={20} />
                Nhật ký hoạt động hệ thống (Audit Logs)
              </h3>
              <p className="text-xs text-slate-400">Bản ghi lịch sử các thao tác của cán bộ điều phối và quản trị viên nhằm truy vết bảo mật.</p>
            </div>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['auditLogs'] })}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
            >
              Làm mới
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-slate-400 font-extrabold uppercase tracking-wider">
                  <th className="py-3 px-4">Mã số</th>
                  <th className="py-3 px-4">Tài khoản</th>
                  <th className="py-3 px-4">Vai trò</th>
                  <th className="py-3 px-4">Thao tác</th>
                  <th className="py-3 px-4">Bảng tác động</th>
                  <th className="py-3 px-4">Địa chỉ IP</th>
                  <th className="py-3 px-4">Thời gian</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {auditLogsLoading ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400">Đang tải nhật ký...</td>
                  </tr>
                ) : !auditLogs || auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-slate-400">Không có nhật ký ghi lại.</td>
                  </tr>
                ) : (
                  auditLogs.map((log: any) => (
                    <tr key={log.id} className="hover:bg-white/5 transition text-slate-300">
                      <td className="py-3 px-4 font-mono font-bold">#{log.id}</td>
                      <td className="py-3 px-4 text-white font-medium">{log.user?.email || 'Ngoại tuyến / Ẩn danh'}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                          log.user?.role === 'admin' 
                            ? 'bg-rose-500/20 text-rose-400' 
                            : 'bg-blue-500/20 text-blue-400'
                        }`}>
                          {log.user?.role || 'N/A'}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-semibold text-slate-200">{log.action}</td>
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-400">{log.target_table || '-'}</td>
                      <td className="py-3 px-4 font-mono text-slate-400">{log.ip_address || '-'}</td>
                      <td className="py-3 px-4 text-slate-400">
                        {new Date(log.created_at).toLocaleString('vi-VN')}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Custom Alert Modal (S5) */}
      {customAlert.isOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1100] p-4">
          <div className="bg-slate-900/95 border border-white/10 rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden text-white animate-fade-in">
            <div className="p-6 text-center space-y-4">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-slate-800 border border-white/10">
                {customAlert.type === 'success' ? (
                  <span className="text-xl">✅</span>
                ) : customAlert.type === 'error' ? (
                  <span className="text-xl">❌</span>
                ) : (
                  <span className="text-xl">ℹ️</span>
                )}
              </div>
              <div className="space-y-2">
                <h3 className="text-base font-bold text-white">{customAlert.title}</h3>
                <p className="text-xs text-slate-400">{customAlert.message}</p>
              </div>
              <button
                onClick={() => setCustomAlert({ ...customAlert, isOpen: false })}
                className="w-full py-2 bg-blue-600 hover:bg-blue-550 text-white rounded-lg text-xs font-bold transition cursor-pointer"
              >
                Xác nhận
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CsgtDashboard;
