import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { incidentsApi } from '../../api/incidents.api';
import { usersApi } from '../../api/users.api';
import { useIncidentStore } from '../../store/incidentStore';
import { useAuthStore } from '../../store/authStore';
import { useGeometry } from '../../hooks/useGeometry';
import { 
  AlertCircle, 
  Trash2, 
  CheckSquare, 
  Square, 
  Plus, 
  X, 
  RefreshCw, 
  Check, 
  MapPin, 
  Info
} from 'lucide-react';
import { fmtTimestampVN } from '../../utils/formatters';

const SEVERITIES: Record<number, { label: string; color: string }> = {
  0: { label: 'Thấp (Nhẹ)', color: 'bg-green-500/10 text-green-400 border-green-500/20' },
  1: { label: 'Thấp (Nhẹ)', color: 'bg-green-500/10 text-green-400 border-green-500/20' },
  2: { label: 'Trung bình', color: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  3: { label: 'Cao (Kẹt cứng)', color: 'bg-red-500/10 text-red-400 border-red-500/20' },
};

const INCIDENT_TYPES = {
  accident: { label: 'Tai nạn', color: 'bg-red-500/15 text-red-300 border-red-500/20' },
  roadblock: { label: 'Cản trở', color: 'bg-amber-500/15 text-amber-300 border-amber-500/20' },
  event: { label: 'Sự kiện', color: 'bg-blue-500/15 text-blue-300 border-blue-500/20' },
  community: { label: 'Cộng đồng', color: 'bg-purple-500/15 text-purple-300 border-purple-500/20' },
};

const STATUSES = {
  active: { label: 'Đang xảy ra', color: 'bg-red-500/10 text-red-400 border-red-500/20' },
  dispatched: { label: 'Đã điều động', color: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  resolved: { label: 'Đã giải quyết', color: 'bg-green-500/10 text-green-400 border-green-500/20' },
};

const Incidents: React.FC = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin';

  const { selectedIncidentIds, filters, toggleSelectIncident, selectAllIncidents, clearSelection, setFilter } = useIncidentStore();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [expandedIds, setExpandedIds] = useState<number[]>([]);

  const toggleExpand = (id: number) => {
    setExpandedIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };
  const [streetQuery, setStreetQuery] = useState('');
  const [streetSuggestions, setStreetSuggestions] = useState<any[]>([]);
  const [selectedStreetId, setSelectedStreetId] = useState<number | null>(null);
  const [selectedStreetName, setSelectedStreetName] = useState('');
  const [selectedOfficerId, setSelectedOfficerId] = useState<number | null>(null);

  // Form states
  const [type, setType] = useState<'accident' | 'roadblock' | 'event' | 'community'>('accident');
  const [severity, setSeverity] = useState(1);
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<'active' | 'dispatched' | 'resolved'>('active');
  const [formError, setFormError] = useState<string | null>(null);

  // Custom confirm modal state
  const [customConfirm, setCustomConfirm] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });

  const showConfirm = (title: string, message: string, onConfirm: () => void) => {
    setCustomConfirm({ isOpen: true, title, message, onConfirm });
  };

  // Queries
  const { data: incidents = [], isLoading, isRefetching } = useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => {
      const params: any = {};
      if (filters.type !== 'all') params.type = filters.type;
      if (filters.status !== 'all') params.status = filters.status;
      if (filters.isActive !== null) params.is_active = filters.isActive;
      return incidentsApi.getIncidents(params);
    },
  });

  const { data: geometry } = useGeometry();

  // Fetch active CSGT officers
  const { data: officers = [] } = useQuery({
    queryKey: ['activeOfficers'],
    queryFn: () => usersApi.getOfficers(),
  });

  // Mutations
  const createIncidentMutation = useMutation({
    mutationFn: (data: any) => incidentsApi.createIncident(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      setIsCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || 'Lỗi khi tạo sự cố.');
    },
  });

  // Batch status update execution
  const updateStatusMutation = useMutation({
    mutationFn: async ({ ids, nextStatus }: { ids: number[]; nextStatus: string }) => {
      await Promise.all(
        ids.map((id) => incidentsApi.updateIncidentStatus(id, nextStatus))
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      clearSelection();
    },
  });

  // Batch delete execution
  const deleteIncidentsMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(ids.map((id) => incidentsApi.deleteIncident(id)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      clearSelection();
    },
  });

  const handleStreetSearch = (text: string) => {
    setStreetQuery(text);
    if (!text.trim() || !geometry) {
      setStreetSuggestions([]);
      setSelectedStreetId(null);
      setSelectedStreetName('');
      return;
    }

    const norm = text.toLowerCase().trim();
    const matches = (geometry.streets ?? []).filter((s) =>
      s.street_name.toLowerCase().includes(norm)
    );

    setStreetSuggestions(matches.slice(0, 5));
  };

  const handleSelectStreet = (street: any) => {
    setSelectedStreetId(street.street_id);
    setSelectedStreetName(street.street_name);
    setStreetQuery(street.street_name);
    setStreetSuggestions([]);
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStreetId) {
      setFormError('Vui lòng nhập và chọn một tên đường hợp lệ từ danh sách gợi ý.');
      return;
    }

    createIncidentMutation.mutate({
      street_id: selectedStreetId,
      type,
      severity,
      description,
      status,
      is_active: status !== 'resolved',
      officer_id: selectedOfficerId,
    });
  };

  const handleBatchStatusUpdate = (nextStatus: string) => {
    if (selectedIncidentIds.length === 0) return;
    updateStatusMutation.mutate({ ids: selectedIncidentIds, nextStatus });
  };

  const handleBatchDelete = () => {
    if (selectedIncidentIds.length === 0 || !isAdmin) return;
    showConfirm(
      'Xác nhận xóa',
      `Bạn có chắc chắn muốn xóa ${selectedIncidentIds.length} sự cố đã chọn?`,
      () => {
        deleteIncidentsMutation.mutate(selectedIncidentIds);
      }
    );
  };

  const resetForm = () => {
    setSelectedStreetId(null);
    setSelectedStreetName('');
    setStreetQuery('');
    setStreetSuggestions([]);
    setType('accident');
    setSeverity(1);
    setDescription('');
    setStatus('active');
    setSelectedOfficerId(null);
    setFormError(null);
  };

  const toggleSelectAll = () => {
    if (selectedIncidentIds.length === incidents.length) {
      clearSelection();
    } else {
      selectAllIncidents(incidents.map((i) => i.id));
    }
  };

  // Find street name from ID helper
  const getStreetName = (streetId: number) => {
    if (!geometry) return `Đường #${streetId}`;
    const street = (geometry.streets ?? []).find((s) => s.street_id === streetId);
    return street ? street.street_name : `Đường #${streetId}`;
  };

  return (
    <div className="min-h-screen pt-20 pb-10 px-4 md:px-8 max-w-7xl mx-auto space-y-6">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
            <AlertCircle className="text-red-400" />
            Quản lý Sự cố Giao thông
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Danh sách tai nạn, cản trở đường và các sự kiện ảnh hưởng tới lưu lượng giao thông toàn thành phố.
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => {
              clearSelection();
              queryClient.invalidateQueries({ queryKey: ['incidents'] });
            }}
            className="p-2 border border-white/10 bg-slate-900/60 rounded-lg text-slate-400 hover:bg-white/5 transition cursor-pointer"
            title="Tải lại danh sách"
          >
            <RefreshCw size={16} className={isRefetching ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded-lg text-sm transition flex items-center gap-1.5 shadow-sm cursor-pointer"
          >
            <Plus size={16} /> Báo cáo sự cố
          </button>
        </div>
      </div>

      {/* Grid Filters Panel */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-xl p-4 shadow-2xl grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Type Filter */}
        <div>
          <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
            Loại sự cố
          </label>
          <select
            value={filters.type}
            onChange={(e) => setFilter('type', e.target.value)}
            className="w-full bg-slate-950/60 text-slate-300 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
          >
            <option value="all">Tất cả loại sự cố</option>
            <option value="accident">Tai nạn</option>
            <option value="roadblock">Vật cản/Khu vực kẹt</option>
            <option value="event">Sự kiện xã hội</option>
            <option value="community">Cộng đồng báo cáo</option>
          </select>
        </div>

        {/* Status Filter */}
        <div>
          <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
            Trạng thái xử lý
          </label>
          <select
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value)}
            className="w-full bg-slate-950/60 text-slate-300 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="active">Đang diễn ra</option>
            <option value="dispatched">Đã điều lực lượng</option>
            <option value="resolved">Đã giải quyết</option>
          </select>
        </div>

        {/* Active state filter */}
        <div>
          <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
            Hiệu lực hoạt động
          </label>
          <select
            value={filters.isActive === null ? 'all' : String(filters.isActive)}
            onChange={(e) => {
              const val = e.target.value;
              setFilter('isActive', val === 'all' ? null : val === 'true');
            }}
            className="w-full bg-slate-950/60 text-slate-300 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
          >
            <option value="all">Tất cả hiệu lực</option>
            <option value="true">Chỉ sự cố đang hoạt động</option>
            <option value="false">Sự cố đã vô hiệu hóa</option>
          </select>
        </div>
      </div>

      {/* Batch Operation Action Panel (Shows only if items are selected) */}
      {selectedIncidentIds.length > 0 && (
        <div className="bg-blue-950/40 border border-blue-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-2xl animate-fade-in text-blue-300">
          <div className="flex items-center gap-2 text-blue-400 text-xs font-bold">
            <CheckSquare size={16} />
            Đã chọn {selectedIncidentIds.length} sự cố
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleBatchStatusUpdate('resolved')}
              className="bg-green-600 hover:bg-green-500 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow-sm transition flex items-center gap-1 cursor-pointer"
            >
              <Check size={14} /> Xác nhận đã giải quyết
            </button>
            <button
              onClick={() => handleBatchStatusUpdate('dispatched')}
              className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow-sm transition flex items-center gap-1 cursor-pointer"
            >
              🚔 Đã điều động CSGT
            </button>
            {isAdmin && (
              <button
                onClick={handleBatchDelete}
                className="bg-red-600 hover:bg-red-500 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow-sm transition flex items-center gap-1 cursor-pointer"
              >
                <Trash2 size={14} /> Xóa sự cố chọn
              </button>
            )}
            <button
              onClick={clearSelection}
              className="border border-white/10 text-slate-400 text-xs font-semibold py-1.5 px-3 bg-slate-900 hover:bg-white/5 rounded-lg cursor-pointer transition"
            >
              Hủy
            </button>
          </div>
        </div>
      )}

      {/* Incidents Table list */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-400 animate-pulse text-sm">
            Đang tải danh sách sự cố giao thông...
          </div>
        ) : incidents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950/80 border-b border-white/10 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="px-4 py-3 w-12 text-center">
                    <button onClick={toggleSelectAll} className="text-slate-400 hover:text-white cursor-pointer transition">
                      {selectedIncidentIds.length === incidents.length ? (
                        <CheckSquare size={16} />
                      ) : (
                        <Square size={16} />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3">Tên đường</th>
                  <th className="px-4 py-3">Loại</th>
                  <th className="px-4 py-3">Nghiêm trọng</th>
                  <th className="px-4 py-3">Mô tả chi tiết</th>
                  <th className="px-4 py-3">Chiến sĩ</th>
                  <th className="px-4 py-3">Trạng thái</th>
                  <th className="px-4 py-3">Thời gian tạo</th>
                  {isAdmin && <th className="px-4 py-3 w-16 text-center">Xóa</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {incidents.map((incident) => {
                  const isChecked = selectedIncidentIds.includes(incident.id);
                  const typeInfo = INCIDENT_TYPES[incident.type as keyof typeof INCIDENT_TYPES] || { label: incident.type, color: 'bg-slate-800 text-slate-300' };
                  const sevInfo = SEVERITIES[incident.severity] || { label: 'Khác', color: 'bg-slate-800 text-slate-400' };
                  const statusInfo = STATUSES[incident.status as keyof typeof STATUSES] || { label: incident.status, color: 'bg-slate-800 text-slate-400' };

                  return (
                    <tr
                      key={`incident-row-${incident.id}`}
                      className={`hover:bg-white/5 transition ${isChecked ? 'bg-blue-500/10' : ''}`}
                    >
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => toggleSelectIncident(incident.id)}
                          className="text-slate-400 hover:text-blue-400 transition cursor-pointer"
                        >
                          {isChecked ? (
                            <CheckSquare className="text-blue-400" size={16} />
                          ) : (
                            <Square size={16} />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3 min-w-[120px] max-w-[180px] break-words">
                        <span className="text-xs font-bold text-slate-200 flex items-start gap-1">
                          <MapPin size={12} className="text-slate-400 mt-0.5 shrink-0" />
                          <span>{getStreetName(incident.street_id)}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${typeInfo.color}`}>
                          {typeInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold ${sevInfo.color}`}>
                          {sevInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 min-w-[150px] max-w-[240px] break-words">
                        {incident.description ? (
                          <div>
                            <p className={`text-xs text-slate-300 ${expandedIds.includes(incident.id) ? '' : 'line-clamp-2'}`}>
                              {incident.description}
                            </p>
                            {incident.description.length > 45 && (
                              <button
                                onClick={() => toggleExpand(incident.id)}
                                className="text-[10px] text-blue-400 hover:text-blue-300 font-semibold mt-1 cursor-pointer transition focus:outline-none"
                              >
                                {expandedIds.includes(incident.id) ? 'Thu gọn' : 'Xem thêm'}
                              </button>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-500 italic text-xs">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs">
                        {(() => {
                          const assignedOfficer = officers.find((off: any) => off.id === incident.officer_id);
                          return assignedOfficer ? (
                            <span className="text-slate-200 font-medium">{assignedOfficer.full_name}</span>
                          ) : (
                            <span className="text-slate-500 font-medium italic">Chưa phân công</span>
                          );
                        })()}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400 whitespace-nowrap">
                        {fmtTimestampVN(incident.start_time)}
                      </td>
                      {isAdmin && (
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => {
                              showConfirm(
                                'Xác nhận xóa',
                                'Bạn có chắc chắn muốn xóa sự cố này?',
                                () => {
                                  deleteIncidentsMutation.mutate([incident.id]);
                                }
                              );
                            }}
                            className="text-red-400 hover:text-red-300 transition cursor-pointer"
                            title="Xóa sự cố"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-2">
            <Info size={24} />
            Không tìm thấy sự cố giao thông nào khớp bộ lọc.
          </div>
        )}
      </div>

      {/* 5. Create Incident Modal Overlay */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4 animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden text-white">
            {/* Header */}
            <div className="bg-slate-950/60 border-b border-white/10 px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                <AlertCircle className="text-red-400" size={18} />
                Báo cáo sự cố mới
              </h4>
              <button
                onClick={() => {
                  setIsCreateModalOpen(false);
                  resetForm();
                }}
                className="text-slate-400 hover:text-white cursor-pointer transition"
              >
                <X size={18} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleCreateSubmit} className="p-5 space-y-4 bg-slate-900/60">
              {formError && (
                <div className="p-2.5 bg-red-950/40 border border-red-500/30 text-red-400 rounded-lg text-xs font-semibold">
                  ⚠️ {formError}
                </div>
              )}

              {/* Target Street autocomplete search */}
              <div className="relative">
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Đường phố kẹt/sự cố
                </label>
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={streetQuery}
                    placeholder="Gõ tìm đường phố..."
                    onChange={(e) => handleStreetSearch(e.target.value)}
                    className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    required
                  />
                  {selectedStreetName && (
                    <span className="absolute right-2 text-[10px] font-bold bg-green-500/20 text-green-400 border border-green-500/30 px-1.5 py-0.5 rounded">
                      Đã chọn
                    </span>
                  )}
                </div>
                {/* Suggestions list */}
                {streetSuggestions.length > 0 && (
                  <div className="absolute left-0 right-0 mt-1 bg-slate-950 border border-white/10 rounded-lg shadow-2xl z-[200] max-h-40 overflow-y-auto custom-scrollbar">
                    {streetSuggestions.map((st) => (
                      <button
                        key={`modal-street-${st.street_id}`}
                        type="button"
                        onClick={() => handleSelectStreet(st)}
                        className="w-full text-left px-3 py-2 text-xs text-slate-300 hover:bg-white/5 border-b border-white/5 last:border-b-0 cursor-pointer"
                      >
                        {st.street_name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Type and Severity */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    Loại sự cố
                  </label>
                  <select
                    value={type}
                    onChange={(e: any) => setType(e.target.value)}
                    className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="accident">Tai nạn giao thông</option>
                    <option value="roadblock">Cản trở/Công trình</option>
                    <option value="event">Sự kiện xã hội</option>
                    <option value="community">Cộng đồng báo cáo</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    Độ nghiêm trọng
                  </label>
                  <select
                    value={severity}
                    onChange={(e: any) => setSeverity(Number(e.target.value))}
                    className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value={0}>Thấp (Chậm nhẹ)</option>
                    <option value={1}>Trung bình</option>
                    <option value={2}>Cao (Kẹt cứng)</option>
                  </select>
                </div>
              </div>

              {/* Status */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Trạng thái sự cố
                </label>
                <select
                  value={status}
                  onChange={(e: any) => setStatus(e.target.value)}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="active">⚠️ Đang xảy ra</option>
                  <option value="dispatched">🚔 Đã điều tuần tra</option>
                  <option value="resolved">✅ Đã giải quyết</option>
                </select>
              </div>

              {/* Officer Assignment */}
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
                    const busy = (incidents ?? []).some(
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
                  Mô tả chi tiết
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Mô tả cụ thể sự việc..."
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>

              {/* Buttons */}
              <div className="pt-2 flex justify-end gap-2 border-t border-white/10 mt-4">
                <button
                  type="button"
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    resetForm();
                  }}
                  className="px-4 py-2 border border-white/10 rounded-lg text-xs font-semibold text-slate-400 hover:bg-white/5 transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createIncidentMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {createIncidentMutation.isPending ? 'Đang tạo...' : 'Tạo báo cáo'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Custom Confirm Modal (S5) */}
      {customConfirm.isOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1100] p-4">
          <div className="bg-slate-900/95 border border-white/10 rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden text-white animate-fade-in">
            <div className="p-6 text-center space-y-4">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-500/10 border border-red-500/20 text-red-400">
                <Trash2 size={24} />
              </div>
              <div className="space-y-2">
                <h3 className="text-base font-bold text-white">{customConfirm.title}</h3>
                <p className="text-xs text-slate-400">{customConfirm.message}</p>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setCustomConfirm({ ...customConfirm, isOpen: false })}
                  className="flex-1 py-2 border border-white/10 hover:bg-slate-800 text-slate-350 rounded-lg text-xs font-semibold transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  onClick={() => {
                    customConfirm.onConfirm();
                    setCustomConfirm({ ...customConfirm, isOpen: false });
                  }}
                  className="flex-1 py-2 bg-red-600 hover:bg-red-550 text-white rounded-lg text-xs font-bold shadow-md transition cursor-pointer"
                >
                  Xác nhận xóa
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Incidents;
