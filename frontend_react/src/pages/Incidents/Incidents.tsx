import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { incidentsApi } from '../../api/incidents.api';
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

const SEVERITIES = [
  { label: 'Thấp (Nhẹ)', color: 'bg-green-50 text-green-700 border-green-200' },
  { label: 'Trung bình', color: 'bg-amber-50 text-amber-600 border-amber-200' },
  { label: 'Cao (Kẹt cứng)', color: 'bg-red-50 text-red-600 border-red-200' },
];

const INCIDENT_TYPES = {
  accident: { label: 'Tai nạn', color: 'bg-red-100 text-red-800' },
  roadblock: { label: 'Cản trở', color: 'bg-amber-100 text-amber-800' },
  event: { label: 'Sự kiện', color: 'bg-blue-100 text-blue-800' },
  community: { label: 'Cộng đồng', color: 'bg-purple-100 text-purple-800' },
};

const STATUSES = {
  active: { label: 'Đang xảy ra', color: 'bg-red-50 text-red-700 border-red-200' },
  dispatched: { label: 'Đã điều động', color: 'bg-blue-50 text-blue-600 border-blue-200' },
  resolved: { label: 'Đã giải quyết', color: 'bg-green-50 text-green-600 border-green-200' },
};

const Incidents: React.FC = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin';

  const { selectedIncidentIds, filters, toggleSelectIncident, selectAllIncidents, clearSelection, setFilter } = useIncidentStore();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [streetQuery, setStreetQuery] = useState('');
  const [streetSuggestions, setStreetSuggestions] = useState<any[]>([]);
  const [selectedStreetId, setSelectedStreetId] = useState<number | null>(null);
  const [selectedStreetName, setSelectedStreetName] = useState('');

  // Form states
  const [type, setType] = useState<'accident' | 'roadblock' | 'event' | 'community'>('accident');
  const [severity, setSeverity] = useState(1);
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<'active' | 'dispatched' | 'resolved'>('active');
  const [formError, setFormError] = useState<string | null>(null);

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
    });
  };

  const handleBatchStatusUpdate = (nextStatus: string) => {
    if (selectedIncidentIds.length === 0) return;
    updateStatusMutation.mutate({ ids: selectedIncidentIds, nextStatus });
  };

  const handleBatchDelete = () => {
    if (selectedIncidentIds.length === 0 || !isAdmin) return;
    if (window.confirm(`Bạn có chắc chắn muốn xóa ${selectedIncidentIds.length} sự cố đã chọn?`)) {
      deleteIncidentsMutation.mutate(selectedIncidentIds);
    }
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
    <div className="min-h-screen bg-gray-50 pt-20 pb-10 px-4 md:px-8 max-w-7xl mx-auto space-y-6">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 flex items-center gap-2">
            <AlertCircle className="text-red-500" />
            Quản lý Sự cố Giao thông
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Danh sách tai nạn, cản trở đường và các sự kiện ảnh hưởng tới lưu lượng giao thông toàn thành phố.
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => {
              clearSelection();
              queryClient.invalidateQueries({ queryKey: ['incidents'] });
            }}
            className="p-2 border border-gray-200 bg-white rounded-lg text-gray-600 hover:bg-gray-50 transition cursor-pointer"
            title="Tải lại danh sách"
          >
            <RefreshCw size={16} className={isRefetching ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg text-sm transition flex items-center gap-1.5 shadow-sm cursor-pointer"
          >
            <Plus size={16} /> Báo cáo sự cố
          </button>
        </div>
      </div>

      {/* Grid Filters Panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Type Filter */}
        <div>
          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
            Loại sự cố
          </label>
          <select
            value={filters.type}
            onChange={(e) => setFilter('type', e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
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
          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
            Trạng thái xử lý
          </label>
          <select
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="active">Đang diễn ra</option>
            <option value="dispatched">Đã điều lực lượng</option>
            <option value="resolved">Đã giải quyết</option>
          </select>
        </div>

        {/* Active state filter */}
        <div>
          <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
            Hiệu lực hoạt động
          </label>
          <select
            value={filters.isActive === null ? 'all' : String(filters.isActive)}
            onChange={(e) => {
              const val = e.target.value;
              setFilter('isActive', val === 'all' ? null : val === 'true');
            }}
            className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
          >
            <option value="all">Tất cả hiệu lực</option>
            <option value="true">Chỉ sự cố đang hoạt động</option>
            <option value="false">Sự cố đã vô hiệu hóa</option>
          </select>
        </div>
      </div>

      {/* Batch Operation Action Panel (Shows only if items are selected) */}
      {selectedIncidentIds.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-sm animate-fade-in">
          <div className="flex items-center gap-2 text-blue-700 text-xs font-bold">
            <CheckSquare size={16} />
            Đã chọn {selectedIncidentIds.length} sự cố
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleBatchStatusUpdate('resolved')}
              className="bg-green-600 hover:bg-green-700 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow transition flex items-center gap-1 cursor-pointer"
            >
              <Check size={14} /> Xác nhận đã giải quyết
            </button>
            <button
              onClick={() => handleBatchStatusUpdate('dispatched')}
              className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow transition flex items-center gap-1 cursor-pointer"
            >
              🚔 Đã điều động CSGT
            </button>
            {isAdmin && (
              <button
                onClick={handleBatchDelete}
                className="bg-red-600 hover:bg-red-700 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow transition flex items-center gap-1 cursor-pointer"
              >
                <Trash2 size={14} /> Xóa sự cố chọn
              </button>
            )}
            <button
              onClick={clearSelection}
              className="border border-gray-300 text-gray-600 text-xs font-semibold py-1.5 px-3 bg-white hover:bg-gray-50 rounded-lg cursor-pointer"
            >
              Hủy
            </button>
          </div>
        </div>
      )}

      {/* Incidents Table list */}
      <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500 animate-pulse text-sm">
            Đang tải danh sách sự cố giao thông...
          </div>
        ) : incidents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                  <th className="px-6 py-4 w-12 text-center">
                    <button onClick={toggleSelectAll} className="text-gray-500 hover:text-gray-800 cursor-pointer">
                      {selectedIncidentIds.length === incidents.length ? (
                        <CheckSquare size={16} />
                      ) : (
                        <Square size={16} />
                      )}
                    </button>
                  </th>
                  <th className="px-6 py-4">Tên đường</th>
                  <th className="px-6 py-4">Loại</th>
                  <th className="px-6 py-4">Nghiêm trọng</th>
                  <th className="px-6 py-4">Mô tả chi tiết</th>
                  <th className="px-6 py-4">Trạng thái</th>
                  <th className="px-6 py-4">Thời gian tạo</th>
                  {isAdmin && <th className="px-6 py-4 w-16 text-center">Xóa</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {incidents.map((incident) => {
                  const isChecked = selectedIncidentIds.includes(incident.id);
                  const typeInfo = INCIDENT_TYPES[incident.type as keyof typeof INCIDENT_TYPES] || { label: incident.type, color: 'bg-gray-100 text-gray-800' };
                  const sevInfo = SEVERITIES[incident.severity] || { label: 'Khác', color: 'bg-gray-50 text-gray-500' };
                  const statusInfo = STATUSES[incident.status as keyof typeof STATUSES] || { label: incident.status, color: 'bg-gray-50 text-gray-500' };

                  return (
                    <tr
                      key={`incident-row-${incident.id}`}
                      className={`hover:bg-gray-50/50 transition ${isChecked ? 'bg-blue-50/20' : ''}`}
                    >
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => toggleSelectIncident(incident.id)}
                          className="text-gray-400 hover:text-blue-600 transition cursor-pointer"
                        >
                          {isChecked ? (
                            <CheckSquare className="text-blue-600" size={16} />
                          ) : (
                            <Square size={16} />
                          )}
                        </button>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs font-bold text-gray-800 flex items-center gap-1">
                          <MapPin size={12} className="text-gray-400" />
                          {getStreetName(incident.street_id)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${typeInfo.color}`}>
                          {typeInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold ${sevInfo.color}`}>
                          {sevInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-xs text-gray-600 max-w-xs truncate" title={incident.description}>
                          {incident.description}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-400">
                        {fmtTimestampVN(incident.start_time)}
                      </td>
                      {isAdmin && (
                        <td className="px-6 py-4 text-center">
                          <button
                            onClick={() => {
                              if (window.confirm('Bạn có chắc chắn muốn xóa sự cố này?')) {
                                deleteIncidentsMutation.mutate([incident.id]);
                              }
                            }}
                            className="text-red-500 hover:text-red-700 transition cursor-pointer"
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
          <div className="p-10 text-center text-gray-400 text-xs flex flex-col items-center justify-center gap-2">
            <Info size={24} />
            Không tìm thấy sự cố giao thông nào khớp bộ lọc.
          </div>
        )}
      </div>

      {/* 5. Create Incident Modal Overlay */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-[1000] p-4 animate-fade-in">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-md w-full overflow-hidden">
            {/* Header */}
            <div className="bg-gray-50 border-b px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-gray-800 flex items-center gap-1.5">
                <AlertCircle className="text-red-500" size={18} />
                Báo cáo sự cố mới
              </h4>
              <button
                onClick={() => {
                  setIsCreateModalOpen(false);
                  resetForm();
                }}
                className="text-gray-400 hover:text-gray-600 cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleCreateSubmit} className="p-5 space-y-4">
              {formError && (
                <div className="p-2.5 bg-red-50 border border-red-200 text-red-600 rounded-lg text-xs font-semibold">
                  ⚠️ {formError}
                </div>
              )}

              {/* Target Street autocomplete search */}
              <div className="relative">
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                  Đường phố kẹt/sự cố
                </label>
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={streetQuery}
                    placeholder="Gõ tìm đường phố..."
                    onChange={(e) => handleStreetSearch(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    required
                  />
                  {selectedStreetName && (
                    <span className="absolute right-2 text-[10px] font-bold bg-green-50 text-green-600 border border-green-200 px-1.5 py-0.5 rounded">
                      Đã chọn
                    </span>
                  )}
                </div>
                {/* Suggestions list */}
                {streetSuggestions.length > 0 && (
                  <div className="absolute left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-[200] max-h-40 overflow-y-auto">
                    {streetSuggestions.map((st) => (
                      <button
                        key={`modal-street-${st.street_id}`}
                        type="button"
                        onClick={() => handleSelectStreet(st)}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 border-b border-gray-100 last:border-b-0 cursor-pointer"
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
                  <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                    Loại sự cố
                  </label>
                  <select
                    value={type}
                    onChange={(e: any) => setType(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="accident">Tai nạn giao thông</option>
                    <option value="roadblock">Cản trở/Công trình</option>
                    <option value="event">Sự kiện xã hội</option>
                    <option value="community">Cộng đồng báo cáo</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                    Độ nghiêm trọng
                  </label>
                  <select
                    value={severity}
                    onChange={(e: any) => setSeverity(Number(e.target.value))}
                    className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value={0}>Thấp (Chậm nhẹ)</option>
                    <option value={1}>Trung bình</option>
                    <option value={2}>Cao (Kẹt cứng)</option>
                  </select>
                </div>
              </div>

              {/* Status */}
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                  Trạng thái sự cố
                </label>
                <select
                  value={status}
                  onChange={(e: any) => setStatus(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="active">⚠️ Đang xảy ra</option>
                  <option value="dispatched">🚔 Đã điều tuần tra</option>
                  <option value="resolved">✅ Đã giải quyết</option>
                </select>
              </div>

              {/* Description */}
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                  Mô tả chi tiết
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Mô tả cụ thể sự việc..."
                  className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>

              {/* Buttons */}
              <div className="pt-2 flex justify-end gap-2 border-t mt-4">
                <button
                  type="button"
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    resetForm();
                  }}
                  className="px-4 py-2 border rounded-lg text-xs font-semibold text-gray-500 hover:bg-gray-50 cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createIncidentMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {createIncidentMutation.isPending ? 'Đang tạo...' : 'Tạo báo cáo'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Incidents;
