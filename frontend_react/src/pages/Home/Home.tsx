import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Menu, X, RotateCcw, AlertTriangle, Thermometer, CloudRain, Shield, RefreshCw, Box, Layers } from 'lucide-react';
import TrafficMap from '../../components/map/TrafficMap';
import { trafficApi } from '../../api/traffic.api';
import { historyApi } from '../../api/history.api';
import { incidentsApi } from '../../api/incidents.api';
import { statsApi } from '../../api/stats.api';
import { feedbackApi } from '../../api/feedback.api';
import { useGeometry } from '../../hooks/useGeometry';
import { DISTRICT_OPTIONS } from '../../constants/map.constants';
import { useAuthStore } from '../../store/authStore';
import { communityApi } from '../../api/community.api';
import { emergencyApi } from '../../api/emergency.api';

const getDistance = (lat1: number, lon1: number, lat2: number, lon2: number) => {
  const R = 6371; // km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

const Home: React.FC = () => {
  const { isLoggedIn, user } = useAuthStore();
  const isCSGTOrAdmin = isLoggedIn && (user?.role === 'csgt' || user?.role === 'admin');

  // Navigation & UI States
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [selectedDistrict, setSelectedDistrict] = useState<number | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isPredictionMode, setIsPredictionMode] = useState(false);
  const [is3D, setIs3D] = useState(false);
  const [sliderValue, setSliderValue] = useState(0); // -6 to 1

  // Community jam reporting states
  const [communityModalOpen, setCommunityModalOpen] = useState(false);
  const [commLat, setCommLat] = useState<number | null>(null);
  const [commLng, setCommLng] = useState<number | null>(null);
  const [commSeverity, setCommSeverity] = useState<number>(1);
  const [commDesc, setCommDesc] = useState('');
  const [commLoading, setCommLoading] = useState(false);
  const [showCommunityReports, setShowCommunityReports] = useState(true);

  // Proximity alerts state
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [proximityAlerts, setProximityAlerts] = useState<{ streetName: string; distance: number }[]>([]);

  // Citizen Reporting Mode States (Existing Feedback)
  const [isReportMode, setIsReportMode] = useState(false);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [reportLat, setReportLat] = useState<number | null>(null);
  const [reportLng, setReportLng] = useState<number | null>(null);
  const [reportStreet, setReportStreet] = useState('');
  const [reportType, setReportType] = useState<'congested' | 'clear' | 'accident'>('congested');
  const [reportDesc, setReportDesc] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Auto-refresh countdown
  const [countdown, setCountdown] = useState(240);

  // Emergency dismissed alert ID
  const [dismissedAlertId, setDismissedAlertId] = useState<number | null>(() => {
    const stored = sessionStorage.getItem('dismissed-alert-id');
    return stored ? Number(stored) : null;
  });

  useEffect(() => {
    const handleBannerDismiss = () => {
      const stored = sessionStorage.getItem('dismissed-alert-id');
      setDismissedAlertId(stored ? Number(stored) : null);
    };
    window.addEventListener('warning-banner-dismissed', handleBannerDismiss);
    return () => window.removeEventListener('warning-banner-dismissed', handleBannerDismiss);
  }, []);

  // Custom alert modal state
  const [customAlert, setCustomAlert] = useState<{ isOpen: boolean; title: string; message: string; type?: 'info' | 'success' | 'error' }>({
    isOpen: false,
    title: '',
    message: '',
  });

  const showAlert = (title: string, message: string, type: 'info' | 'success' | 'error' = 'info') => {
    setCustomAlert({ isOpen: true, title, message, type });
  };

  // Queries
  const { data: trafficState, refetch: refetchTrafficState } = useQuery({
    queryKey: ['traffic-state'],
    queryFn: () => trafficApi.getState(),
  });

  const { data: communityReports, refetch: refetchCommunityReports } = useQuery({
    queryKey: ['community-reports'],
    queryFn: () => communityApi.getReports(),
    refetchInterval: 30000,
    enabled: showCommunityReports && isCSGTOrAdmin,
  });

  const { data: predictionData } = useQuery({
    queryKey: ['predictions'],
    queryFn: () => trafficApi.getPredict30Min(),
    enabled: isPredictionMode && sliderValue === 0,
  });

  // Query for 6-hour historical traffic data
  const { data: historyTrafficState } = useQuery({
    queryKey: ['traffic-history', sliderValue],
    queryFn: () => historyApi.getTrafficHistory(Math.abs(sliderValue)),
    enabled: sliderValue < 0,
    staleTime: 300000,
  });

  // Query active emergency alert
  const { data: activeAlert } = useQuery({
    queryKey: ['active-alert'],
    queryFn: () => emergencyApi.getActiveAlert(),
    refetchInterval: 30000,
  });

  // Query for 5min future prediction
  const { data: prediction5MinData } = useQuery({
    queryKey: ['predictions-5min'],
    queryFn: () => historyApi.getPrediction5Min(),
    enabled: sliderValue === 1,
    staleTime: 60000,
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

  const { data: geometry } = useGeometry();

  // 5. Submit Citizen Report Mutation
  const createFeedbackMutation = useMutation({
    mutationFn: (data: any) => feedbackApi.createFeedback(data),
    onSuccess: () => {
      // Calculate congested segments within 3km
      let congestedNearbyCount = 0;
      const radiusKm = 3;
      if (reportLat !== null && reportLng !== null && trafficState?.streets && geometry?.streets) {
        trafficState.streets.forEach((s: any) => {
          const geomStreet = geometry.streets.find((gs: any) => gs.street_id === s.street_id);
          if (!geomStreet || !geomStreet.path || geomStreet.path.length === 0) return;

          const segments = s.segments || [];
          if (segments.length <= 1) {
            if (s.congestion_level === 2) {
              let isNearby = false;
              for (let i = 0; i < geomStreet.path.length; i++) {
                const pt = geomStreet.path[i];
                const dist = getDistance(reportLat, reportLng, pt[1], pt[0]);
                if (dist <= radiusKm) {
                  isNearby = true;
                  break;
                }
              }
              if (isNearby) {
                congestedNearbyCount++;
              }
            }
          } else {
            const totalPoints = geomStreet.path.length;
            const totalSegs = segments.length;
            const nearbyCongestedSegs = new Set<number>();

            for (let i = 0; i < totalPoints; i++) {
              const pt = geomStreet.path[i];
              const dist = getDistance(reportLat, reportLng, pt[1], pt[0]);
              if (dist <= radiusKm) {
                const segIdx = Math.min(Math.floor((i / totalPoints) * totalSegs), totalSegs - 1);
                const seg = segments.find((sg: any) => sg.segment_idx === segIdx);
                if (seg && seg.congestion_level === 2) {
                  nearbyCongestedSegs.add(segIdx);
                }
              }
            }
            congestedNearbyCount += nearbyCongestedSegs.size;
          }
        });
      }
      const successMsg = congestedNearbyCount > 0
        ? `Cảm ơn bạn! Phản ánh của bạn đã được gửi thành công đến hệ thống. Phát hiện có ${congestedNearbyCount} đoạn đường ù tắc gần bạn trong bán kính ${radiusKm}km.`
        : `Cảm ơn bạn! Phản ánh của bạn đã được gửi thành công đến hệ thống. Khu vực xung quanh bạn trong bán kính ${radiusKm}km hiện đang thông thoáng.`;

      showAlert('Đã gửi phản ánh', successMsg, 'success');
      setReportModalOpen(false);
      setIsReportMode(false);
      setReportDesc('');
      setReportStreet('');
      setSubmitError(null);
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      let msg = 'Không thể gửi phản ánh. Vui lòng thử lại sau.';
      if (typeof detail === 'string') msg = detail;
      else if (Array.isArray(detail)) msg = detail.map((d: any) => d.msg).join(', ');
      setSubmitError(msg);
    },
  });

  const handleReportClick = (lat: number, lng: number, streetName?: string) => {
    setReportLat(lat);
    setReportLng(lng);
    setReportStreet(streetName || '');
    setReportModalOpen(true);
    setSubmitError(null);
  };

  const handleReportSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (reportLat === null || reportLng === null) return;

    let matchedStreetId: number | null = null;
    if (reportStreet.trim() !== '' && geometry?.streets) {
      const found = geometry.streets.find(
        (s) => s.street_name.toLowerCase().trim() === reportStreet.toLowerCase().trim()
      );
      if (found) matchedStreetId = found.street_id;
    }

    createFeedbackMutation.mutate({
      street_id: matchedStreetId,
      lat: reportLat,
      lon: reportLng,
      report_type: reportType,
      description: reportDesc,
    });
  };

  const handleReportAtCurrentLocation = () => {
    if (!navigator.geolocation) {
      showAlert('Lỗi định vị', 'Trình duyệt của bạn không hỗ trợ định vị GPS.', 'error');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCommLat(position.coords.latitude);
        setCommLng(position.coords.longitude);
        setCommunityModalOpen(true);
      },
      (error) => {
        console.error('Error getting location:', error);
        showAlert('Quyền định vị', 'Không thể lấy vị trí hiện tại. Vui lòng cấp quyền truy cập vị trí cho ứng dụng.', 'info');
      },
      { enableHighAccuracy: true }
    );
  };

  const handleCommunitySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (commLat === null || commLng === null) return;
    setCommLoading(true);
    try {
      await communityApi.createReport(commLat, commLng, commSeverity, commDesc);
      // Calculate congested segments within 3km
      let congestedNearbyCount = 0;
      const radiusKm = 3;
      if (trafficState?.streets && geometry?.streets) {
        trafficState.streets.forEach((s: any) => {
          const geomStreet = geometry.streets.find((gs: any) => gs.street_id === s.street_id);
          if (!geomStreet || !geomStreet.path || geomStreet.path.length === 0) return;

          const segments = s.segments || [];
          if (segments.length <= 1) {
            if (s.congestion_level === 2) {
              let isNearby = false;
              for (let i = 0; i < geomStreet.path.length; i++) {
                const pt = geomStreet.path[i];
                const dist = getDistance(commLat, commLng, pt[1], pt[0]);
                if (dist <= radiusKm) {
                  isNearby = true;
                  break;
                }
              }
              if (isNearby) {
                congestedNearbyCount++;
              }
            }
          } else {
            const totalPoints = geomStreet.path.length;
            const totalSegs = segments.length;
            const nearbyCongestedSegs = new Set<number>();

            for (let i = 0; i < totalPoints; i++) {
              const pt = geomStreet.path[i];
              const dist = getDistance(commLat, commLng, pt[1], pt[0]);
              if (dist <= radiusKm) {
                const segIdx = Math.min(Math.floor((i / totalPoints) * totalSegs), totalSegs - 1);
                const seg = segments.find((sg: any) => sg.segment_idx === segIdx);
                if (seg && seg.congestion_level === 2) {
                  nearbyCongestedSegs.add(segIdx);
                }
              }
            }
            congestedNearbyCount += nearbyCongestedSegs.size;
          }
        });
      }
      const successMsg = congestedNearbyCount > 0
        ? `Cảm ơn bạn! Báo cáo kẹt xe đã được gửi thành công. Phát hiện có ${congestedNearbyCount} đoạn đường ù tắc gần bạn trong bán kính ${radiusKm}km.`
        : `Cảm ơn bạn! Báo cáo kẹt xe đã được gửi thành công. Khu vực xung quanh bạn trong bán kính ${radiusKm}km hiện đang thông thoáng.`;

      showAlert('Thành công', successMsg, 'success');
      setCommunityModalOpen(false);
      setCommDesc('');
      setCommSeverity(1);
      refetchCommunityReports();
    } catch (err) {
      console.error('Error submitting community report:', err);
      showAlert('Lỗi', 'Gửi báo cáo thất bại. Vui lòng thử lại sau.', 'error');
    } finally {
      setCommLoading(false);
    }
  };

  // 1. Periodic user location updates for proximity alerts
  useEffect(() => {
    if (!navigator.geolocation) return;

    const updateLocation = () => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
          });
        },
        (err) => console.log('Location access not granted for proximity alerts.', err),
        { enableHighAccuracy: true }
      );
    };

    updateLocation();
    const interval = setInterval(updateLocation, 25000); // Check every 25s
    return () => clearInterval(interval);
  }, []);

  // 2. Compute Haversine distance to red congested segments (within 2km)
  useEffect(() => {
    if (!userLocation || !trafficState?.streets || !geometry?.streets) return;

    const alerts: { streetName: string; distance: number }[] = [];
    const redStreets = trafficState.streets.filter((s: any) => s.congestion_level === 2);

    redStreets.forEach((rs: any) => {
      const geomStreet = geometry.streets.find((s: any) => s.street_id === rs.street_id);
      if (!geomStreet || !geomStreet.path || geomStreet.path.length === 0) return;

      // Find minimum distance to any point on the segment
      let minDistance = Infinity;
      geomStreet.path.forEach((pt: number[]) => {
        const dist = getDistance(userLocation.lat, userLocation.lng, pt[1], pt[0]);
        if (dist < minDistance) {
          minDistance = dist;
        }
      });

      if (minDistance <= 2.0) {
        alerts.push({
          streetName: geomStreet.street_name,
          distance: minDistance,
        });
      }
    });

    setProximityAlerts(alerts);
  }, [userLocation, trafficState, geometry]);

  // Countdown logic
  useEffect(() => {
    if (sliderValue !== 0) return; // Pause countdown when viewing history or predictions

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
  }, [refetchTrafficState, sliderValue]);

  // Calculate live stats
  const totalStreets = (sliderValue === 1 ? prediction5MinData?.length : (sliderValue < 0 ? historyTrafficState?.total : trafficState?.total)) ?? 0;
  const redCount = (sliderValue === 1 ? prediction5MinData?.filter((p) => p.predicted_level === 2).length : ((sliderValue < 0 ? historyTrafficState : trafficState)?.streets?.filter((s) => s.congestion_level === 2).length)) ?? 0;
  const yellowCount = (sliderValue === 1 ? prediction5MinData?.filter((p) => p.predicted_level === 1).length : ((sliderValue < 0 ? historyTrafficState : trafficState)?.streets?.filter((s) => s.congestion_level === 1).length)) ?? 0;

  const avgSpeed = (() => {
    if (sliderValue === 1) return 0;
    const targetState = sliderValue < 0 ? historyTrafficState : trafficState;
    if (!targetState?.streets || targetState.streets.length === 0) return 0;
    const validStreets = targetState.streets.filter(s => s.avg_speed > 0);
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

  const hasActiveAlert = !!(activeAlert && activeAlert.is_active && dismissedAlertId !== activeAlert.id);

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* 1. Map container (fills screen) */}
      <div className="absolute inset-0 z-0">
        <TrafficMap
          districtId={selectedDistrict}
          congestionLevel={selectedLevel}
          searchQuery={searchQuery}
          isPredictionMode={sliderValue === 1 ? true : (sliderValue === 0 ? isPredictionMode : false)}
          predictionData={sliderValue === 1 ? prediction5MinData : (sliderValue === 0 ? predictionData : null)}
          isReportMode={isReportMode}
          onReportClick={handleReportClick}
          is3D={is3D}
          trafficState={sliderValue < 0 ? historyTrafficState : null}
          communityReports={communityReports}
          showCommunityReports={showCommunityReports}
        />
      </div>

      {/* 2. Left side filter panel overlay */}
      <div
        className={`absolute ${hasActiveAlert ? 'top-[100px] h-[calc(100vh-100px)]' : 'top-16 h-[calc(100vh-64px)]'} left-0 w-full sm:w-80 bg-slate-950/80 backdrop-blur-md border-r border-white/10 shadow-2xl transition-all duration-300 ease-in-out z-40 flex flex-col ${
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

          {/* Community Reports Layer Toggle (S5-55b) */}
          {isCSGTOrAdmin && (
            <div className="border-t border-white/10 pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="block text-sm font-semibold text-slate-200">Báo cáo từ cộng đồng</span>
                  <span className="text-xs text-slate-400">Xem tin kẹt xe từ người dân</span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showCommunityReports}
                    onChange={(e) => setShowCommunityReports(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
                </label>
              </div>
            </div>
          )}
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
        className={`absolute ${hasActiveAlert ? 'top-[116px]' : 'top-20'} left-4 z-30 bg-slate-900/80 hover:bg-slate-800/80 backdrop-blur-sm border border-white/10 shadow-lg rounded-full p-3 text-slate-200 transition-all duration-300 cursor-pointer`}
        title="Bộ lọc bản đồ"
      >
        <Menu size={20} />
      </button>

      {/* Citizen Report Mode Toggle Button */}
      <button
        onClick={() => {
          setIsReportMode(!isReportMode);
          if (isFilterOpen) setIsFilterOpen(false);
        }}
        className={`absolute ${hasActiveAlert ? 'top-[180px]' : 'top-36'} left-4 z-30 backdrop-blur-sm border shadow-lg rounded-full p-3 transition-all duration-300 cursor-pointer ${
          isReportMode
            ? 'bg-red-600 hover:bg-red-500 border-red-500 text-white animate-pulse'
            : 'bg-slate-900/80 hover:bg-slate-800/80 border-white/10 text-slate-200'
        }`}
        title={isReportMode ? 'Tắt chế độ báo cáo kẹt xe' : 'Bật chế độ báo cáo kẹt xe'}
      >
        <AlertTriangle size={20} />
      </button>

      {/* 2D/3D Toggle Button */}
      <button
        onClick={() => setIs3D(!is3D)}
        className={`absolute ${hasActiveAlert ? 'top-[244px]' : 'top-52'} left-4 z-30 backdrop-blur-sm border shadow-lg rounded-full p-3 transition-all duration-300 cursor-pointer ${
          is3D
            ? 'bg-indigo-600 hover:bg-indigo-500 border-indigo-500 text-white shadow-indigo-500/20'
            : 'bg-slate-900/80 hover:bg-slate-800/80 border-white/10 text-slate-200'
        }`}
        title={is3D ? 'Chuyển sang bản đồ 2D' : 'Chuyển sang bản đồ 3D'}
      >
        {is3D ? <Layers size={20} /> : <Box size={20} />}
      </button>

      {/* Community Jam Report floating button (S5-53b) */}
      <button
        onClick={handleReportAtCurrentLocation}
        style={{ top: hasActiveAlert ? '308px' : '272px' }}
        className="absolute left-4 z-30 bg-slate-900/80 hover:bg-slate-800/80 text-slate-200 backdrop-blur-sm border border-white/10 shadow-lg rounded-full p-3 transition-all duration-300 cursor-pointer flex items-center justify-center"
        title="Báo cáo kẹt xe tại vị trí hiện tại"
      >
        <span className="text-lg">📍</span>
      </button>

      {/* Report Mode Top Banner Overlay */}
      {isReportMode && (
        <div className={`absolute ${hasActiveAlert ? 'top-[180px]' : 'top-36'} left-16 z-30 bg-red-600/95 backdrop-blur-md border border-red-500/30 text-white rounded-xl px-4 py-2 text-xs font-bold shadow-2xl animate-pulse flex items-center gap-2 max-w-[280px] sm:max-w-sm transition-all duration-300`}>
          <span>🚨</span>
          <span className="leading-tight">Chế độ báo cáo kẹt xe đang bật. Hãy click vào bản đồ để báo cáo!</span>
          <button
            onClick={() => setIsReportMode(false)}
            className="ml-auto font-bold underline hover:text-slate-200 cursor-pointer shrink-0"
          >
            Hủy
          </button>
        </div>
      )}

      {/* 6. Citizen Report Modal Form */}
      {reportModalOpen && reportLat !== null && reportLng !== null && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4 animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden text-white">
            {/* Modal Header */}
            <div className="bg-slate-950/60 border-b border-white/10 px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                📢 Gửi phản ánh giao thông
              </h4>
              <button
                onClick={() => {
                  setReportModalOpen(false);
                  setSubmitError(null);
                }}
                className="text-slate-400 hover:text-white transition cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleReportSubmit} className="p-5 space-y-4 bg-slate-900/60">
              {submitError && (
                <div className="p-2.5 bg-red-950/40 border border-red-500/30 text-red-400 rounded-lg text-xs font-semibold">
                  ⚠️ {submitError}
                </div>
              )}

              {/* Coordinates */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    Vĩ độ (Latitude)
                  </label>
                  <input
                    type="text"
                    value={reportLat.toFixed(6)}
                    disabled
                    className="w-full bg-slate-950/60 text-slate-400 border border-white/10 rounded-lg px-3 py-2 cursor-not-allowed font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    Kinh độ (Longitude)
                  </label>
                  <input
                    type="text"
                    value={reportLng.toFixed(6)}
                    disabled
                    className="w-full bg-slate-950/60 text-slate-400 border border-white/10 rounded-lg px-3 py-2 cursor-not-allowed font-mono"
                  />
                </div>
              </div>

              {/* Street Name input */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Tên đường phản ánh
                </label>
                <input
                  type="text"
                  value={reportStreet}
                  onChange={(e) => setReportStreet(e.target.value)}
                  placeholder="Ví dụ: Bạch Đằng"
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Nhập chính xác tên đường để hệ thống cập nhật đúng vị trí
                </span>
              </div>

              {/* Report Type */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Mức độ giao thông thực tế
                </label>
                <select
                  value={reportType}
                  onChange={(e: any) => setReportType(e.target.value)}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="congested">🔴 Kẹt xe / Ùn tắc</option>
                  <option value="accident">⚠️ Có tai nạn giao thông</option>
                  <option value="clear">🟢 Đường thông thoáng</option>
                </select>
              </div>

              {/* Description */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Mô tả chi tiết / Ghi chú
                </label>
                <textarea
                  value={reportDesc}
                  onChange={(e) => setReportDesc(e.target.value)}
                  placeholder="Ghi chú thêm về sự cố để hỗ trợ CSGT..."
                  rows={3}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setReportModalOpen(false);
                    setSubmitError(null);
                  }}
                  className="flex-1 py-2 border border-white/10 hover:bg-slate-800 text-slate-300 rounded-lg text-xs font-semibold transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createFeedbackMutation.isPending}
                  className="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {createFeedbackMutation.isPending ? 'Đang gửi...' : 'Gửi phản ánh 🚀'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 4. Top-Right KPI cards overlay */}
      <div className={`absolute ${hasActiveAlert ? 'top-[116px]' : 'top-20'} right-4 z-30 flex flex-col gap-2 pointer-events-none transition-all duration-300`}>
        {/* KPI Panel */}
        <div className="flex flex-col sm:flex-row gap-2 pointer-events-auto">
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
        {sliderValue === 0 ? (
          <>
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
          </>
        ) : sliderValue === 1 ? (
          <>
            <Shield size={14} className="text-purple-400 animate-pulse" />
            <span className="text-purple-400 font-bold">Chế độ dự báo AI tương lai (+5 phút)</span>
            <button
              onClick={() => setSliderValue(0)}
              className="hover:text-slate-200 text-slate-400 transition font-bold cursor-pointer underline ml-1"
            >
              Về hiện tại
            </button>
          </>
        ) : (
          <>
            <RotateCcw size={14} className="text-amber-500" />
            <span className="text-amber-400 font-bold">Lịch sử: {Math.abs(sliderValue)} giờ trước</span>
            <button
              onClick={() => setSliderValue(0)}
              className="hover:text-slate-200 text-slate-400 transition font-bold cursor-pointer underline ml-1"
            >
              Về hiện tại
            </button>
          </>
        )}
      </div>

      {/* 6. Time Slider Widget (Bottom Center, 40% Width) */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-[40%] min-w-[340px] max-w-lg z-30 bg-slate-950/90 backdrop-blur-md border border-white/10 shadow-2xl rounded-2xl px-5 py-3 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs font-bold">
          <span className="text-slate-400">Trục thời gian</span>
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] ${
            sliderValue === 0
              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : sliderValue === 1
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30 animate-pulse'
                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
          }`}>
            {sliderValue === 0
              ? '● Hiện tại (Thời gian thực)'
              : sliderValue === 1
                ? '🔮 Dự đoán (+5 phút)'
                : `⏱ Lịch sử (${Math.abs(sliderValue)} giờ trước)`
            }
          </span>
        </div>

        <div className="relative mt-1">
          <input
            type="range"
            min="-6"
            max="1"
            step="1"
            value={sliderValue}
            onChange={(e) => setSliderValue(parseInt(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500 focus:outline-none"
          />
          <div className="flex justify-between text-[9px] text-slate-400 font-semibold mt-1 px-0.5">
            <span>-6h</span>
            <span>-5h</span>
            <span>-4h</span>
            <span>-3h</span>
            <span>-2h</span>
            <span>-1h</span>
            <span className={sliderValue === 0 ? 'text-green-400 font-bold' : ''}>Hiện tại</span>
            <span className={sliderValue === 1 ? 'text-purple-400 font-bold' : ''}>+5p</span>
          </div>
        </div>
      </div>

      {/* Prediction indicator */}
      {(sliderValue === 1 || (isPredictionMode && sliderValue === 0)) && (
        <div className={`absolute bottom-4 right-4 z-30 text-white shadow-lg rounded-lg px-4 py-2 flex items-center gap-2 text-xs font-bold animate-pulse ${
          sliderValue === 1 ? 'bg-purple-600' : 'bg-blue-600'
        }`}>
          <Shield size={14} />
          <span>{sliderValue === 1 ? 'DỰ BÁO AI (+5 PHÚT)' : 'DỰ BÁO AI (+30 PHÚT)'}</span>
        </div>
      )}

      {/* Community Jam Report Modal (S5-53b) */}
      {communityModalOpen && commLat !== null && commLng !== null && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4">
          <div className="bg-slate-900/95 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden text-white animate-fade-in">
            <div className="bg-slate-950/60 border-b border-white/10 px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                🚨 Báo cáo kẹt xe cộng đồng
              </h4>
              <button
                onClick={() => setCommunityModalOpen(false)}
                className="text-slate-400 hover:text-white transition cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCommunitySubmit} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Vĩ độ</label>
                  <input
                    type="text"
                    value={commLat.toFixed(6)}
                    disabled
                    className="w-full bg-slate-950/60 text-slate-400 border border-white/10 rounded-lg px-3 py-2 cursor-not-allowed font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Kinh độ</label>
                  <input
                    type="text"
                    value={commLng.toFixed(6)}
                    disabled
                    className="w-full bg-slate-950/60 text-slate-400 border border-white/10 rounded-lg px-3 py-2 cursor-not-allowed font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Mức độ kẹt xe</label>
                <select
                  value={commSeverity}
                  onChange={(e) => setCommSeverity(Number(e.target.value))}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-amber-500 cursor-pointer"
                >
                  <option value={1}>🟢 Nhẹ (Di chuyển chậm)</option>
                  <option value={2}>🟡 Vừa (Ùn ứ cục bộ)</option>
                  <option value={3}>🔴 Nặng (Kẹt cứng/Không di chuyển được)</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Ghi chú chi tiết</label>
                <textarea
                  value={commDesc}
                  onChange={(e) => setCommDesc(e.target.value)}
                  placeholder="Ghi chú vị trí, hướng di chuyển hoặc nguyên nhân nếu biết..."
                  rows={3}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-amber-500 resize-none"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setCommunityModalOpen(false)}
                  className="flex-1 py-2 border border-white/10 hover:bg-slate-800 text-slate-300 rounded-lg text-xs font-semibold transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={commLoading}
                  className="flex-1 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {commLoading ? 'Đang gửi...' : 'Gửi báo cáo 🚀'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Proximity Alert Toast (S5-56) */}
      {proximityAlerts.length > 0 && (
        <div className="fixed bottom-6 right-[72px] z-50 max-w-[280px] sm:max-w-xs bg-slate-900/95 backdrop-blur-md border border-red-500/30 rounded-2xl shadow-2xl p-3 text-white">
          <div className="flex items-start space-x-2">
            <span className="text-xl">🚨</span>
            <div className="flex-1">
              <h5 className="font-bold text-sm text-red-400 flex items-center gap-1">
                Cảnh báo ùn tắc gần bạn
              </h5>
              <div className="mt-1.5 space-y-1.5 max-h-28 overflow-y-auto pr-1">
                {proximityAlerts.slice(0, 3).map((alert, idx) => (
                  <p key={idx} className="text-xs text-slate-300">
                    Đường <strong className="text-white">{alert.streetName}</strong> đang kẹt xe cách bạn <strong className="text-amber-400">{alert.distance.toFixed(1)} km</strong>.
                  </p>
                ))}
                {proximityAlerts.length > 3 && (
                  <p className="text-[10px] text-slate-400">Và {proximityAlerts.length - 3} điểm kẹt xe khác.</p>
                )}
              </div>
            </div>
            <button
              onClick={() => setProximityAlerts([])}
              className="text-slate-400 hover:text-white transition cursor-pointer"
            >
              <X size={16} />
            </button>
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

export default Home;
