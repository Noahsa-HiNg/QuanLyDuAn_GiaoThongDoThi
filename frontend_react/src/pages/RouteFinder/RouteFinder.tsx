import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useMapStore } from '../../store/mapStore';
import { routingApi } from '../../api/routing.api';
import { normalizeVN } from '../../utils/formatters';
import TrafficMap from '../../components/map/TrafficMap';
import RouteLayer from '../../components/map/RouteLayer';
import { CONGESTION_COLORS } from '../../constants/map.constants';
import { getCongestionLabel } from '../../utils/congestionColor';
import { 
  ArrowUpDown, 
  MapPin, 
  Compass, 
  Navigation, 
  Info, 
  Trash2, 
  RefreshCw, 
  ListOrdered
} from 'lucide-react';

const RouteFinder: React.FC = () => {
  const {
    fromPos,
    toPos,
    fromName,
    toName,
    routeShortest,
    routeFastest,
    selectedMode,
    setFromPos,
    setToPos,
    setFromName,
    setToName,
    setRouteShortest,
    setRouteFastest,
    setSelectedMode,
    clearRoute,
    resetAll,
  } = useMapStore();

  const [fromQuery, setFromQuery] = useState('');
  const [toQuery, setToQuery] = useState('');
  const [fromSuggestions, setFromSuggestions] = useState<any[]>([]);
  const [toSuggestions, setToSuggestions] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Sync inputs with store names (especially when clicking the map)
  useEffect(() => {
    setFromQuery(fromName);
  }, [fromName]);

  useEffect(() => {
    setToQuery(toName);
  }, [toName]);

  // 1. Fetch all street midpoints for autocomplete
  const { data: midpoints = [] } = useQuery({
    queryKey: ['midpoints'],
    queryFn: () => routingApi.getMidpoints(),
  });



  // Handle fuzzy search suggestions
  const handleInputChange = (
    text: string,
    setQuery: React.Dispatch<React.SetStateAction<string>>,
    setSuggestions: React.Dispatch<React.SetStateAction<any[]>>,
    posSetter: (pos: [number, number] | null) => void,
    nameSetter: (name: string) => void
  ) => {
    setQuery(text);
    if (!text.trim()) {
      setSuggestions([]);
      posSetter(null);
      nameSetter('');
      clearRoute();
      return;
    }

    const norm = normalizeVN(text);
    const matches = midpoints.filter((street) => 
      street.name && normalizeVN(street.name).includes(norm)
    );

    setSuggestions(matches.slice(0, 5));
  };

  const selectStreet = (
    street: any,
    setQuery: React.Dispatch<React.SetStateAction<string>>,
    setSuggestions: React.Dispatch<React.SetStateAction<any[]>>,
    posSetter: (pos: [number, number] | null) => void,
    nameSetter: (name: string) => void
  ) => {
    setQuery(street.name);
    posSetter([street.lat, street.lng]);
    nameSetter(street.name);
    setSuggestions([]);
    clearRoute();
  };

  const handleSwap = () => {
    const tempPos = fromPos;
    const tempName = fromName;

    setFromPos(toPos);
    setFromName(toName);
    setFromQuery(toName);

    setToPos(tempPos);
    setToName(tempName);
    setToQuery(tempName);

    clearRoute();
  };

  const handleFindRoute = async () => {
    if (!fromPos || !toPos) return;

    setIsSearching(true);
    setSearchError(null);

    try {
      // Call shortest and fastest routes in parallel
      const [shortest, fastest] = await Promise.all([
        routingApi.getRoute(fromPos[0], fromPos[1], toPos[0], toPos[1], 'shortest'),
        routingApi.getRoute(fromPos[0], fromPos[1], toPos[0], toPos[1], 'fastest'),
      ]);

      setRouteShortest(shortest);
      setRouteFastest(fastest);
    } catch (err: any) {
      setSearchError(err.response?.data?.detail || 'Không thể kết nối đến máy chủ tìm đường.');
    } finally {
      setIsSearching(false);
    }
  };

  const getRouteStreetStatus = () => {
    const activeRoute = selectedMode === 'shortest' ? routeShortest : routeFastest;
    if (!activeRoute || !activeRoute.streets) return [];

    return activeRoute.streets
      .filter((st) => st.name !== '[intersection]')
      .map((st) => ({
        name: st.name,
        congestion_level: st.congestion_level,
        avg_speed: st.avg_speed,
      }));
  };

  const streetStatuses = getRouteStreetStatus();
  const hasResults = routeShortest && routeFastest && !searchError;

  // Determine recommendation (Faster duration is recommended)
  const isShortestRecommended = routeShortest && routeFastest && routeShortest.estimated_time_min <= routeFastest.estimated_time_min;

  return (
    <div className="w-full h-[calc(100vh-64px)] mt-16 flex flex-col md:flex-row overflow-hidden">
      {/* 1. Left Form Panel */}
      <div className="w-full md:w-[420px] bg-slate-950/80 backdrop-blur-md border-r border-white/10 shadow-2xl flex flex-col h-full overflow-y-auto text-white">
        <div className="p-5 flex-grow">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-xl font-extrabold text-white flex items-center gap-2">
              <span className="text-2xl">🗺️</span>
              Tìm đường thông minh
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Thuật toán A* tối ưu hóa thời gian và khoảng cách đi lại tại Đà Nẵng.
            </p>
          </div>

          {/* Form */}
          <div className="space-y-4 relative">
            {/* Start Point */}
            <div className="relative">
              <label className="block text-[10px] font-bold tracking-wider text-green-400 uppercase mb-1 flex items-center gap-1">
                <MapPin size={10} /> Điểm xuất phát
              </label>
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={fromQuery}
                  placeholder="Gõ tên đường hoặc click chọn trên map..."
                  onChange={(e) =>
                    handleInputChange(
                      e.target.value,
                      setFromQuery,
                      setFromSuggestions,
                      setFromPos,
                      setFromName
                    )
                  }
                  className="w-full pl-3 pr-8 py-2 text-sm bg-slate-900/60 border border-white/10 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
                {fromQuery && (
                  <button
                    onClick={() => {
                      setFromQuery('');
                      setFromPos(null);
                      setFromName('');
                      clearRoute();
                    }}
                    className="absolute right-2 text-slate-400 hover:text-slate-200 cursor-pointer"
                  >
                    ✕
                  </button>
                )}
              </div>
              {/* Autocomplete Suggestions */}
              {fromSuggestions.length > 0 && (
                <div className="absolute left-0 right-0 mt-1 bg-slate-900 border border-white/10 rounded-lg shadow-2xl z-[200] max-h-48 overflow-y-auto">
                  {fromSuggestions.map((street) => (
                    <button
                      key={`from-sug-${street.id}`}
                      onClick={() =>
                        selectStreet(
                          street,
                          setFromQuery,
                          setFromSuggestions,
                          setFromPos,
                          setFromName
                        )
                      }
                      className="w-full text-left px-3 py-2 text-xs hover:bg-slate-800 border-b last:border-b-0 border-white/5 flex items-center justify-between cursor-pointer text-slate-200"
                    >
                      <span className="font-medium text-slate-200">{street.name}</span>
                      <span className="text-[10px] text-slate-500">Midpoint</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Swap Button Container */}
            <div className="flex justify-center -my-2 relative z-10">
              <button
                type="button"
                onClick={handleSwap}
                className="p-1.5 bg-slate-900 border border-white/10 rounded-full text-slate-400 hover:text-slate-200 hover:bg-slate-800 shadow-sm transition transform hover:rotate-180 duration-300 cursor-pointer"
                title="Hoán đổi điểm xuất phát và điểm đến"
              >
                <ArrowUpDown size={14} />
              </button>
            </div>

            {/* Destination Point */}
            <div className="relative">
              <label className="block text-[10px] font-bold tracking-wider text-red-400 uppercase mb-1 flex items-center gap-1">
                <MapPin size={10} /> Điểm đến
              </label>
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={toQuery}
                  placeholder="Gõ tên đường hoặc click chọn trên map..."
                  onChange={(e) =>
                    handleInputChange(
                      e.target.value,
                      setToQuery,
                      setToSuggestions,
                      setToPos,
                      setToName
                    )
                  }
                  className="w-full pl-3 pr-8 py-2 text-sm bg-slate-900/60 border border-white/10 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
                {toQuery && (
                  <button
                    onClick={() => {
                      setToQuery('');
                      setToPos(null);
                      setToName('');
                      clearRoute();
                    }}
                    className="absolute right-2 text-slate-400 hover:text-slate-200 cursor-pointer"
                  >
                    ✕
                  </button>
                )}
              </div>
              {/* Autocomplete Suggestions */}
              {toSuggestions.length > 0 && (
                <div className="absolute left-0 right-0 mt-1 bg-slate-900 border border-white/10 rounded-lg shadow-2xl z-[200] max-h-48 overflow-y-auto">
                  {toSuggestions.map((street) => (
                    <button
                      key={`to-sug-${street.id}`}
                      onClick={() =>
                        selectStreet(
                          street,
                          setToQuery,
                          setToSuggestions,
                          setToPos,
                          setToName
                        )
                      }
                      className="w-full text-left px-3 py-2 text-xs hover:bg-slate-800 border-b last:border-b-0 border-white/5 flex items-center justify-between cursor-pointer text-slate-200"
                    >
                      <span className="font-medium text-slate-200">{street.name}</span>
                      <span className="text-[10px] text-slate-500">Midpoint</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="pt-2 flex gap-2">
              <button
                onClick={handleFindRoute}
                disabled={!fromPos || !toPos || isSearching}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white font-semibold py-2 px-4 rounded-lg text-sm transition flex items-center justify-center gap-1.5 shadow-sm disabled:cursor-not-allowed cursor-pointer"
              >
                {isSearching ? (
                  <>
                    <RefreshCw size={15} className="animate-spin" />
                    Đang tính toán...
                  </>
                ) : (
                  <>
                    <Navigation size={15} />
                    Tìm đường đi
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setFromQuery('');
                  setToQuery('');
                  resetAll();
                }}
                className="px-3 py-2 border border-white/10 rounded-lg text-slate-400 bg-slate-900 hover:bg-slate-800 hover:text-slate-200 transition cursor-pointer"
                title="Đặt lại bộ lọc"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>

          {/* Hint Overlay Details */}
          {!hasResults && !searchError && (
            <div className="mt-8 bg-blue-950/40 border border-blue-900/40 rounded-xl p-4 flex gap-3 text-blue-300 text-xs">
              <Info size={18} className="flex-shrink-0" />
              <div>
                <p className="font-bold mb-1">Mẹo chọn điểm đi/đến:</p>
                <ul className="list-disc pl-4 space-y-1 text-slate-300">
                  <li>Gõ tên các tuyến đường chính (ví dụ: Lê Duẩn, Nguyễn Văn Linh).</li>
                  <li>Hoặc click trực tiếp lên bản đồ bên phải để cắm mốc xuất phát và đích.</li>
                </ul>
              </div>
            </div>
          )}

          {/* Error Message */}
          {searchError && (
            <div className="mt-4 p-3 bg-red-950/40 border border-red-900/40 text-red-400 rounded-lg text-xs font-semibold">
              ⚠️ {searchError}
            </div>
          )}

          {/* 3. Results Comparison Cards */}
          {hasResults && (
            <div className="mt-6 space-y-4">
              <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                <Compass size={12} /> Bảng so sánh tuyến
              </h3>

              <div className="grid grid-cols-2 gap-3">
                {/* Shortest Route Card */}
                <div
                  onClick={() => setSelectedMode('shortest')}
                  className={`p-3 rounded-xl border-2 text-left cursor-pointer transition flex flex-col justify-between ${
                    selectedMode === 'shortest'
                      ? 'border-indigo-500 bg-indigo-500/10'
                      : 'border-white/10 bg-slate-900/40 hover:border-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-indigo-400 flex items-center gap-1">
                      📏 Ngắn nhất
                    </span>
                    {isShortestRecommended && (
                      <span className="text-[9px] font-bold bg-indigo-950/80 text-indigo-400 border border-indigo-500/30 px-1.5 py-0.5 rounded-full">
                        ⭐ Tốt nhất
                      </span>
                    )}
                  </div>
                  <div>
                    <div className="text-xl font-black text-indigo-200 leading-none">
                      {Number((routeShortest.total_distance_m / 1000).toFixed(2))} <span className="text-xs font-normal text-indigo-400">km</span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">
                      Thời gian: {Math.round(routeShortest.estimated_time_min)} phút
                    </div>
                  </div>
                </div>

                {/* Fastest Route Card */}
                <div
                  onClick={() => setSelectedMode('fastest')}
                  className={`p-3 rounded-xl border-2 text-left cursor-pointer transition flex flex-col justify-between ${
                    selectedMode === 'fastest'
                      ? 'border-green-500 bg-green-500/10'
                      : 'border-white/10 bg-slate-900/40 hover:border-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-green-400 flex items-center gap-1">
                      ⚡ Nhanh nhất
                    </span>
                    {!isShortestRecommended && (
                      <span className="text-[9px] font-bold bg-green-950/80 text-green-400 border border-green-500/30 px-1.5 py-0.5 rounded-full">
                        ⭐ Tốt nhất
                      </span>
                    )}
                  </div>
                  <div>
                    <div className="text-xl font-black text-green-200 leading-none">
                      {Math.round(routeFastest.estimated_time_min)} <span className="text-xs font-normal text-green-400">phút</span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-1">
                      Khoảng cách: {Number((routeFastest.total_distance_m / 1000).toFixed(2))} km
                    </div>
                  </div>
                </div>
              </div>

              {/* Mode indicator label */}
              <div className="p-2.5 bg-slate-900/60 rounded-lg text-[10px] text-slate-400 text-center border border-white/5">
                Tuyến đường đang vẽ: <b className={selectedMode === 'shortest' ? 'text-indigo-400' : 'text-green-400'}>
                  {selectedMode === 'shortest' ? '📏 Ngắn nhất' : '⚡ Nhanh nhất'}
                </b>
              </div>
            </div>
          )}
        </div>

        {/* 4. Scrollable List of Streets Passed */}
        {hasResults && streetStatuses.length > 0 && (
          <div className="border-t border-white/10 bg-slate-950/40 p-5 flex flex-col">
            <h4 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-1">
              <ListOrdered size={12} /> Các đường đi qua ({streetStatuses.length})
            </h4>
            <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto pr-1">
              {streetStatuses.map((st: any, idx: number) => (
                <div
                  key={`route-street-${idx}`}
                  className="bg-slate-900/40 border border-white/5 rounded-lg p-2 flex flex-col justify-between shadow-sm"
                >
                  <div className="text-[11px] font-semibold text-slate-200 truncate" title={st.name}>
                    {st.name}
                  </div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{
                        backgroundColor:
                          st.congestion_level !== null
                            ? CONGESTION_COLORS[st.congestion_level]
                            : CONGESTION_COLORS['null'],
                      }}
                    />
                    <span className="text-[9px] font-medium text-slate-400 truncate">
                      {st.congestion_level !== null
                        ? `${getCongestionLabel(st.congestion_level)} · ${st.avg_speed}km/h`
                        : 'Không có data'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 2. Right Map Panel */}
      <div className="flex-grow h-full relative">
        <TrafficMap hideTrafficLines={true}>
          {(map) => (
            <RouteLayer map={map} />
          )}
        </TrafficMap>
      </div>
    </div>
  );
};

export default RouteFinder;
