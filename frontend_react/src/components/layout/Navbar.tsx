import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { LogOut, User, Navigation, BarChart2, Shield, AlertCircle, Users, Calendar, Map } from 'lucide-react';

const Navbar: React.FC = () => {
  const { user, isLoggedIn, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

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
  );
};

export default Navbar;
