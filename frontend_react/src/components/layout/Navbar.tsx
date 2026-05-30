import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store/authStore';
import { incidentsApi } from '../../api/incidents.api';
import { fmtTimestampVN } from '../../utils/formatters';
import { LogOut, User, Navigation, BarChart2, Shield, AlertCircle, Users, Calendar, Map, X, Bell } from 'lucide-react';

const Navbar: React.FC = () => {
  const { user, isLoggedIn, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const queryClient = useQueryClient();
  const [dismissedIncidentIds, setDismissedIncidentIds] = useState<number[]>([]);

  // Poll for active incidents assigned to this user
  const { data: myIncidents = [] } = useQuery({
    queryKey: ['my-incidents', user?.id],
    queryFn: () => incidentsApi.getIncidents({ is_active: true }),
    enabled: isLoggedIn && user?.role === 'csgt',
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Filter for dispatched incidents assigned to this officer that are not dismissed yet
  const pendingDispatches = myIncidents.filter(
    (inc) =>
      inc.officer_id === user?.id &&
      inc.status === 'dispatched' &&
      !dismissedIncidentIds.includes(inc.id)
  );

  const acceptIncidentMutation = useMutation({
    mutationFn: (id: number) => incidentsApi.updateIncidentStatus(id, 'active'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-incidents'] });
      queryClient.invalidateQueries({ queryKey: ['activeIncidents'] });
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
    },
  });

  const isActive = (path: string) => location.pathname === path;

  const linkClass = (path: string) =>
    `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
      isActive(path)
        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
        : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'
    }`;

  const isCSGTOrAdmin = user?.role === 'csgt' || user?.role === 'admin';
  const isAdmin = user?.role === 'admin';

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 h-16 bg-slate-950/80 backdrop-blur-md border-b border-white/10 shadow-2xl flex items-center justify-between px-6 z-navbar z-[100]">
      {/* Left: Brand */}
      <Link to="/" className="flex items-center gap-2">
        <span className="text-xl">🚦</span>
        <span className="font-extrabold text-lg bg-gradient-to-r from-blue-400 via-indigo-400 to-emerald-400 bg-clip-text text-transparent">
          AI TRAFFIC DA NANG
        </span>
      </Link>

      {/* Center: Navigation Links */}
      <div className="hidden md:flex items-center gap-1">
        <Link to="/" className={linkClass('/')}>
          <Map size={16} />
          Bản đồ
        </Link>
        <Link to="/route-finder" className={linkClass('/route-finder')}>
          <Navigation size={16} />
          Tìm đường
        </Link>
        {isCSGTOrAdmin && (
          <>
            <Link to="/dashboard" className={linkClass('/dashboard')}>
              <BarChart2 size={16} />
              Thống kê
            </Link>
            <Link to="/csgt-dashboard" className={linkClass('/csgt-dashboard')}>
              <Shield size={16} />
              CSGT
            </Link>
            <Link to="/incidents" className={linkClass('/incidents')}>
              <AlertCircle size={16} />
              Sự cố
            </Link>
          </>
        )}

        {isAdmin && (
          <>
            <Link to="/admin/users" className={linkClass('/admin/users')}>
              <Users size={16} />
              Tài khoản
            </Link>
            <Link to="/admin/scheduler" className={linkClass('/admin/scheduler')}>
              <Calendar size={16} />
              Scheduler
            </Link>
          </>
        )}
      </div>

      {/* Right: Auth Profile */}
      <div className="flex items-center gap-3">
        {isLoggedIn && user ? (
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <span className="block text-sm font-semibold text-slate-200">{user.full_name || user.email}</span>
              <span className="block text-[10px] font-bold text-blue-400 uppercase tracking-wider">{user.role}</span>
            </div>
            <div className="h-9 w-9 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 font-bold border border-blue-500/20">
              {(user.full_name || user.email || 'U').charAt(0).toUpperCase()}
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-lg text-sm font-medium transition cursor-pointer"
            >
              <LogOut size={15} />
              Đăng xuất
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-semibold transition shadow-sm"
          >
            <User size={16} />
            Đăng nhập
          </Link>
        )}
      </div>
    </nav>

    {/* Real-time CSGT Dispatch Toasts */}
    {pendingDispatches.length > 0 && (
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-4 max-w-sm w-full pointer-events-none">
        {pendingDispatches.map((inc) => (
          <div
            key={`dispatch-toast-${inc.id}`}
            className="pointer-events-auto bg-slate-900/95 backdrop-blur-xl border border-blue-500/30 rounded-2xl shadow-2xl p-5 text-white animate-slide-up flex flex-col gap-3 relative overflow-hidden"
          >
            <div className="absolute top-0 left-0 w-1.5 h-full bg-blue-500" />
            <div className="flex justify-between items-start gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">🚔</span>
                <div>
                  <h4 className="text-xs font-black text-blue-400 uppercase tracking-wider">
                    Lệnh điều động mới
                  </h4>
                  <span className="text-[10px] text-slate-400 font-medium">
                    Thời gian: {fmtTimestampVN(inc.start_time)}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setDismissedIncidentIds((prev) => [...prev, inc.id])}
                className="text-slate-400 hover:text-white transition cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>
            <p className="text-xs text-slate-200 font-medium leading-relaxed">
              {inc.description}
            </p>
            <div className="flex gap-2.5 pt-1">
              <button
                onClick={() => setDismissedIncidentIds((prev) => [...prev, inc.id])}
                className="flex-1 py-1.5 border border-white/10 hover:bg-white/5 text-slate-300 rounded-lg text-[10px] font-bold transition cursor-pointer"
              >
                Bỏ qua
              </button>
              <button
                onClick={() => acceptIncidentMutation.mutate(inc.id)}
                disabled={acceptIncidentMutation.isPending}
                className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold shadow-md transition cursor-pointer disabled:opacity-50"
              >
                {acceptIncidentMutation.isPending ? 'Đang xác nhận...' : 'Đã nhận lệnh 🫡'}
              </button>
            </div>
          </div>
        ))}
      </div>
    )}
  </>
);
};

export default Navbar;
