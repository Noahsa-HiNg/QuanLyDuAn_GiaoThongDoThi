import React, { useEffect, useState } from 'react';
import { emergencyApi, type EmergencyBanner } from '../../api/emergency.api';
import { X } from 'lucide-react';

const EmergencyBannerView: React.FC = () => {
  const [banner, setBanner] = useState<EmergencyBanner | null>(null);
  const [isDismissed, setIsDismissed] = useState(false);

  const fetchBanner = async () => {
    try {
      const data = await emergencyApi.getActiveAlert();
      setBanner(data);
    } catch (error) {
      console.error('Error fetching emergency banner:', error);
    }
  };

  useEffect(() => {
    fetchBanner();
    const interval = setInterval(fetchBanner, 30000); // Poll mỗi 30s
    return () => clearInterval(interval);
  }, []);

  // Handle dismissal sync with sessionStorage
  useEffect(() => {
    if (banner) {
      const dismissedId = sessionStorage.getItem('dismissed-alert-id');
      if (dismissedId === String(banner.id)) {
        setIsDismissed(true);
      } else {
        setIsDismissed(false);
      }
    }
  }, [banner]);

  // Handle dynamic body class adding/removing for layout shifts
  useEffect(() => {
    if (banner && !isDismissed) {
      document.body.classList.add('has-warning-banner');
    } else {
      document.body.classList.remove('has-warning-banner');
    }
    return () => {
      document.body.classList.remove('has-warning-banner');
    };
  }, [banner, isDismissed]);

  const handleDismiss = () => {
    if (banner) {
      sessionStorage.setItem('dismissed-alert-id', String(banner.id));
      setIsDismissed(true);
    }
  };

  if (!banner || isDismissed) return null;

  return (
    <div className="fixed top-0 left-0 right-0 h-9 bg-gradient-to-r from-red-700 via-rose-600 to-red-700 text-white border-b border-red-800 shadow-xl flex items-center px-4 z-[9999] transition-all duration-300">
      <div className="max-w-7xl mx-auto flex items-center justify-center space-x-3 text-center w-full relative">
        <span className="flex h-2 w-2 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-100"></span>
        </span>
        <span className="text-sm">⚠️</span>
        <div className="text-xs sm:text-sm font-bold tracking-wide flex items-center flex-wrap justify-center gap-1.5 pr-6">
          <span className="uppercase text-yellow-300 font-extrabold px-1.5 py-0.5 rounded bg-red-900/40 text-[9px] tracking-wider">
            KHẨN CẤP
          </span>
          <span className="font-extrabold text-white uppercase text-[11px] sm:text-xs">{banner.title}:</span>
          <span className="font-normal text-rose-50 text-[11px] sm:text-xs truncate max-w-[240px] sm:max-w-md md:max-w-none">{banner.content}</span>
        </div>
        
        <button
          onClick={handleDismiss}
          className="absolute right-0 top-1/2 -translate-y-1/2 text-rose-200 hover:text-white transition cursor-pointer p-1"
          title="Đóng thông báo"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
};

export default EmergencyBannerView;
