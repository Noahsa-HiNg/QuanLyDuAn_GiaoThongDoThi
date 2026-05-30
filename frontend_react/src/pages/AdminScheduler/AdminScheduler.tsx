import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { schedulerApi } from '../../api/scheduler.api';
import { 
  Calendar, 
  Play, 
  Pause, 
  Zap, 
  Activity, 
  CheckCircle, 
  AlertTriangle, 
  Clock, 
  RefreshCw, 
  Database,
  ArrowRight
} from 'lucide-react';
import { fmtTimestampVN } from '../../utils/formatters';

const AdminScheduler: React.FC = () => {
  const queryClient = useQueryClient();
  const [crawlSuccessMsg, setCrawlSuccessMsg] = useState<string | null>(null);

  // Queries
  const { data: scheduleState, isLoading: isStateLoading } = useQuery({
    queryKey: ['schedulerState'],
    queryFn: () => schedulerApi.getState(),
    refetchInterval: 10000, // 10s auto-refresh
  });

  const { data: jobs = [], isLoading: isJobsLoading } = useQuery({
    queryKey: ['schedulerJobs'],
    queryFn: () => schedulerApi.getJobs(),
  });

  const { data: crawlStatus, isLoading: isStatusLoading } = useQuery({
    queryKey: ['crawlStatus'],
    queryFn: () => schedulerApi.getCrawlStatus(),
    refetchInterval: 10000,
  });

  // Mutations
  const pauseMutation = useMutation({
    mutationFn: () => schedulerApi.pauseSchedule(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedulerState'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => schedulerApi.resumeSchedule(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedulerState'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
    },
  });

  const crawlNowMutation = useMutation({
    mutationFn: () => schedulerApi.crawlNow(),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['crawlStatus'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
      
      const count = res.data?.streets_updated ?? 0;
      setCrawlSuccessMsg(`⚡ Kích hoạt cào dữ liệu thành công! Đã cập nhật ${count} tuyến đường vào lúc ${new Date().toLocaleTimeString('vi-VN')}.`);
      
      // Auto clear message after 6s
      setTimeout(() => setCrawlSuccessMsg(null), 6000);
    },
  });

  const handleToggleState = () => {
    if (!scheduleState) return;
    if (scheduleState.paused) {
      resumeMutation.mutate();
    } else {
      pauseMutation.mutate();
    }
  };

  const handleCrawlNow = () => {
    if (crawlNowMutation.isPending) return;
    setCrawlSuccessMsg(null);
    crawlNowMutation.mutate();
  };

  return (
    <div className="min-h-screen pt-20 pb-10 px-4 md:px-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
            <Calendar className="text-blue-400" />
            Quản trị Scheduler & Crawler
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Điều phối chu kỳ cào dữ liệu giao thông tự động, theo dõi các tác vụ nền và kích hoạt đồng bộ hóa thủ công.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['schedulerState'] });
              queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
              queryClient.invalidateQueries({ queryKey: ['crawlStatus'] });
            }}
            className="p-2 border border-white/10 bg-slate-900/60 rounded-lg text-slate-400 hover:bg-white/5 transition cursor-pointer"
            title="Làm mới trạng thái"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Scheduler Dashboard KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* State status card */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-5 shadow-2xl flex items-center justify-between text-white">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-lg ${
              scheduleState?.paused 
                ? 'bg-amber-500/10 text-amber-400' 
                : 'bg-green-500/10 text-green-400'
            }`}>
              <Activity size={24} />
            </div>
            <div>
              <span className="block text-xs font-medium text-slate-400">Scheduler</span>
              <span className="block text-lg font-black text-slate-250 mt-0.5">
                {isStateLoading ? 'Đang kiểm tra...' : scheduleState?.paused ? 'TẠM DỪNG' : 'ĐANG CHẠY'}
              </span>
            </div>
          </div>
          <button
            onClick={handleToggleState}
            disabled={isStateLoading || pauseMutation.isPending || resumeMutation.isPending}
            className={`px-3 py-2 rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
              scheduleState?.paused
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-amber-500 hover:bg-amber-400 text-white'
            }`}
          >
            {scheduleState?.paused ? (
              <>
                <Play size={14} /> Kích hoạt lại
              </>
            ) : (
              <>
                <Pause size={14} /> Tạm dừng
              </>
            )}
          </button>
        </div>

        {/* Crawl Status status card */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-5 shadow-2xl flex items-center gap-3 text-white">
          <div className={`p-3 rounded-lg ${
            crawlStatus?.status === 'success' 
              ? 'bg-green-500/10 text-green-400' 
              : 'bg-red-500/10 text-red-400'
          }`}>
            <Database size={24} />
          </div>
          <div>
            <span className="block text-xs font-medium text-slate-400">Trạng thái đồng bộ</span>
            <span className="block text-lg font-black text-slate-200 mt-0.5">
              {isStatusLoading ? '...' : crawlStatus?.status === 'success' ? 'ĐỒNG BỘ THÀNH CÔNG' : 'CÓ LỖI'}
            </span>
            <span className="text-[10px] text-slate-500 font-medium">
              Đã cập nhật: {crawlStatus?.streets_updated ?? 0} tuyến đường
            </span>
          </div>
        </div>

        {/* Last sync run card */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-5 shadow-2xl flex items-center gap-3 text-white">
          <div className="p-3 rounded-lg bg-blue-500/10 text-blue-400">
            <Clock size={24} />
          </div>
          <div>
            <span className="block text-xs font-medium text-slate-400">Lần đồng bộ cuối</span>
            <span className="block text-xs font-bold text-slate-350 mt-1 max-w-[200px] truncate" title={crawlStatus?.last_run ? fmtTimestampVN(crawlStatus.last_run) : 'N/A'}>
              {crawlStatus?.last_run ? fmtTimestampVN(crawlStatus.last_run) : 'Chưa chạy lần nào'}
            </span>
          </div>
        </div>
      </div>

      {/* Manual Trigger Panel */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div>
            <h3 className="text-sm font-extrabold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Zap size={16} className="text-yellow-400" />
              Đồng bộ dữ liệu tức thì
            </h3>
            <p className="text-xs text-slate-450 mt-1">
              Bỏ qua chu kỳ scheduler, chạy trực tiếp luồng crawler để cào dữ liệu ùn tắc mới nhất từ nguồn API Mapbox.
            </p>
          </div>

          <button
            onClick={handleCrawlNow}
            disabled={crawlNowMutation.isPending}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-550 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {crawlNowMutation.isPending ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                Đang cào dữ liệu...
              </>
            ) : (
              <>
                <Zap size={14} /> Chạy cào ngay lập tức
              </>
            )}
          </button>
        </div>

        {/* Success / Error notification */}
        {crawlSuccessMsg && (
          <div className="p-3.5 bg-green-950/40 border border-green-500/30 text-green-400 rounded-xl text-xs font-semibold flex items-center gap-2 animate-fade-in">
            <CheckCircle size={16} />
            {crawlSuccessMsg}
          </div>
        )}
        {crawlNowMutation.isError && (
          <div className="p-3.5 bg-red-950/40 border border-red-500/30 text-red-400 rounded-xl text-xs font-semibold flex items-center gap-2 animate-fade-in">
            <AlertTriangle size={16} />
            Lỗi đồng bộ: {(crawlNowMutation.error as any).response?.data?.detail || 'Không thể cào dữ liệu giao thông.'}
          </div>
        )}
      </div>

      {/* Scheduler Jobs List */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/10 bg-slate-950/40">
          <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
            <Clock size={14} />
            Danh sách tác vụ lập lịch nền ({jobs.length})
          </h3>
        </div>

        {isJobsLoading ? (
          <div className="p-8 text-center text-slate-400 animate-pulse text-sm">
            Đang tải danh sách tác vụ nền...
          </div>
        ) : jobs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950/80 border-b border-white/10 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-4 w-48">Job ID</th>
                  <th className="px-6 py-4">Tên tác vụ</th>
                  <th className="px-6 py-4">Chu kỳ kích hoạt</th>
                  <th className="px-6 py-4">Lần chạy tiếp theo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {jobs.map((job) => (
                  <tr key={`job-${job.id}`} className="hover:bg-white/5 transition text-xs">
                    <td className="px-6 py-4 font-mono text-slate-550 font-bold">#{job.id}</td>
                    <td className="px-6 py-4 font-bold text-slate-200">{job.name}</td>
                    <td className="px-6 py-4 text-slate-300">
                      <span className="bg-blue-500/10 text-blue-400 font-semibold px-2 py-0.5 rounded border border-blue-500/20 text-[10px]">
                        {job.trigger}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-400">
                      {job.next_run_time ? (
                        <span className="flex items-center gap-1">
                          <ArrowRight size={12} className="text-slate-500" />
                          {fmtTimestampVN(job.next_run_time)}
                        </span>
                      ) : (
                        <span className="text-red-400 font-semibold italic">Tạm dừng / Hủy kích hoạt</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center text-slate-400 text-xs">
            Không có tác vụ lập lịch nền nào hoạt động.
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminScheduler;
