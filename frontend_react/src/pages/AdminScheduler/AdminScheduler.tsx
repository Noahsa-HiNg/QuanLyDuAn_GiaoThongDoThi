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
  ArrowRight,
  Terminal,
  Brain
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend 
} from 'recharts';
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

  const { data: statsData } = useQuery({
    queryKey: ['crawlStats'],
    queryFn: () => schedulerApi.getCrawlStats(),
    refetchInterval: 30000, // 30s auto-refresh
  });

  const { data: logsData, refetch: refetchLogs } = useQuery({
    queryKey: ['crawlLogs'],
    queryFn: () => schedulerApi.getCrawlLogs(150),
    refetchInterval: 10000,
  });

  const { data: modelMetrics, refetch: refetchMetrics } = useQuery({
    queryKey: ['modelMetrics'],
    queryFn: () => schedulerApi.getModelMetrics(),
    refetchInterval: 30000,
  });

  const { data: modelStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['modelStatus'],
    queryFn: () => schedulerApi.getModelStatus(),
    refetchInterval: 30000,
  });

  const [runJobSuccessMsg, setRunJobSuccessMsg] = useState<string | null>(null);

  const runJobMutation = useMutation({
    mutationFn: (jobId: string) => schedulerApi.runJobNow(jobId),
    onSuccess: (res, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
      setRunJobSuccessMsg(`⚡ Đã gửi yêu cầu kích hoạt chạy tác vụ #${jobId} thành công!`);
      setTimeout(() => setRunJobSuccessMsg(null), 5500);
      if (jobId === 'auto_retrain') {
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ['modelMetrics'] });
          queryClient.invalidateQueries({ queryKey: ['modelStatus'] });
        }, 3000);
      }
    },
  });

  const logEndRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logsData?.logs]);

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
              queryClient.invalidateQueries({ queryKey: ['modelMetrics'] });
              queryClient.invalidateQueries({ queryKey: ['modelStatus'] });
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

      {/* 2. Crawler Log Statistics KPIs (Dashboard) */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        {/* KPI: Total runs */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-4 shadow-xl text-white">
          <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tổng chu kỳ</span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-xl font-black text-white">{statsData?.kpis.total_runs ?? 0}</span>
            <span className="text-[10px] text-slate-500 font-semibold">lượt</span>
          </div>
        </div>

        {/* KPI: Success runs */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-4 shadow-xl text-white">
          <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Thành công</span>
          <div className="flex items-baseline gap-1 mt-1 text-emerald-400">
            <span className="text-xl font-black">{statsData?.kpis.success_runs ?? 0}</span>
            <span className="text-[10px] font-semibold">lượt</span>
          </div>
        </div>

        {/* KPI: Failed runs */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-4 shadow-xl text-white">
          <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Thất bại</span>
          <div className="flex items-baseline gap-1 mt-1 text-rose-500">
            <span className="text-xl font-black">{statsData?.kpis.failed_runs ?? 0}</span>
            <span className="text-[10px] font-semibold">lượt</span>
          </div>
        </div>

        {/* KPI: Missed runs */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-4 shadow-xl text-white">
          <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Bỏ lỡ</span>
          <div className="flex items-baseline gap-1 mt-1 text-amber-500">
            <span className="text-xl font-black">{statsData?.kpis.missed_runs ?? 0}</span>
            <span className="text-[10px] font-semibold">lượt</span>
          </div>
        </div>

        {/* KPI: Success rate */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-4 shadow-xl text-white">
          <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tỉ lệ đạt</span>
          <div className="flex items-baseline gap-1 mt-1 text-blue-400">
            <span className="text-xl font-black">{statsData?.kpis.success_rate ?? 100}%</span>
          </div>
        </div>

        {/* KPI: Avg duration */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-white/10 p-4 shadow-xl text-white">
          <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Thời gian TB</span>
          <div className="flex items-baseline gap-1 mt-1 text-indigo-400">
            <span className="text-xl font-black">{statsData?.kpis.avg_duration ?? 0}</span>
            <span className="text-[10px] font-semibold">giây</span>
          </div>
        </div>
      </div>

      {/* 3. Recharts Dashboard Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Performance */}
        <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-5 flex flex-col">
          <h4 className="text-xs font-extrabold text-slate-450 uppercase tracking-wider mb-4 text-white">
            📈 Tần suất cào & Hiệu năng (50 lượt gần nhất)
          </h4>
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={statsData?.last_runs ?? []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorDuration" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="timestamp" stroke="#64748b" fontSize={9} />
                <YAxis yAxisId="left" stroke="#10b981" fontSize={9} />
                <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" fontSize={9} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }} 
                  labelStyle={{ color: '#94a3b8', fontSize: 11, fontWeight: 'bold' }}
                  itemStyle={{ fontSize: 11 }}
                />
                <Legend wrapperStyle={{ fontSize: 10, paddingTop: 10 }} />
                <Area yAxisId="left" type="monotone" dataKey="success_count" name="Số đường cào được" stroke="#10b981" fillOpacity={1} fill="url(#colorSuccess)" />
                <Area yAxisId="right" type="monotone" dataKey="duration" name="Thời gian cào (giây)" stroke="#3b82f6" fillOpacity={1} fill="url(#colorDuration)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Daily Sync Status */}
        <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-5 flex flex-col">
          <h4 className="text-xs font-extrabold text-slate-450 uppercase tracking-wider mb-4 text-white">
            📊 Trạng thái đồng bộ (7 ngày gần nhất)
          </h4>
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statsData?.daily_stats ?? []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={9} />
                <YAxis stroke="#64748b" fontSize={9} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '8px' }} 
                  labelStyle={{ color: '#94a3b8', fontSize: 11, fontWeight: 'bold' }}
                  itemStyle={{ fontSize: 11 }}
                />
                <Legend wrapperStyle={{ fontSize: 10, paddingTop: 10 }} />
                <Bar dataKey="success" name="Thành công" fill="#10b981" stackId="a" />
                <Bar dataKey="failed" name="Thất bại" fill="#ef4444" stackId="a" />
                <Bar dataKey="missed" name="Bỏ lỡ" fill="#f59e0b" stackId="a" />
              </BarChart>
            </ResponsiveContainer>
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

      {/* AI Model Training & Metrics Panel */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <h3 className="text-sm font-extrabold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Brain size={16} className="text-pink-400" />
              Thông số Huấn luyện AI Models dự báo kẹt xe
            </h3>
            <p className="text-xs text-slate-450 mt-1">
              Đồng bộ dữ liệu thực tế TomTom để huấn luyện định kỳ các mô hình dự báo AI (LightGBM, XGBoost, CatBoost).
            </p>
          </div>

          <button
            onClick={() => runJobMutation.mutate('auto_retrain')}
            disabled={runJobMutation.isPending && runJobMutation.variables === 'auto_retrain'}
            className="px-4 py-2 bg-pink-600 hover:bg-pink-550 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {runJobMutation.isPending && runJobMutation.variables === 'auto_retrain' ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                Đang huấn luyện lại...
              </>
            ) : (
              <>
                <Brain size={14} /> Huấn luyện lại tất cả Model
              </>
            )}
          </button>
        </div>

        {/* Model info cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {['10min', '20min', '30min'].map((horizon) => {
            const label = horizon === '10min' ? 'Dự báo 10 Phút' : horizon === '20min' ? 'Dự báo 20 Phút' : 'Dự báo 30 Phút';
            const metrics = modelMetrics?.[horizon];
            const status = modelStatus?.[horizon];
            const isReady = status?.ready;

            return (
              <div key={`model-card-${horizon}`} className="bg-slate-950/60 rounded-xl border border-white/5 p-4 flex flex-col justify-between space-y-3">
                <div className="flex items-center justify-between border-b border-white/5 pb-2">
                  <span className="text-xs font-bold text-slate-350">{label}</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-extrabold tracking-wider ${
                    isReady ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
                  }`}>
                    {isReady ? 'SẴN SÀNG' : 'CHƯA TRAIN'}
                  </span>
                </div>

                {metrics && !metrics.error ? (
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Mô hình tốt nhất:</span>
                      <span className="font-mono text-blue-400 font-bold">{metrics.model_name || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Weighted F1-score:</span>
                      <span className="font-bold text-green-400">
                        {metrics.f1_score ? `${(metrics.f1_score * 100).toFixed(1)}%` : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Độ chính xác:</span>
                      <span className="font-bold text-slate-300">
                        {metrics.accuracy ? `${(metrics.accuracy * 100).toFixed(1)}%` : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between pt-1 text-[10px] text-slate-500 border-t border-white/5 mt-1.5">
                      <span>Cập nhật cuối:</span>
                      <span>{metrics.trained_at ? fmtTimestampVN(metrics.trained_at) : 'N/A'}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6 text-slate-500 text-xs italic">
                    {metrics?.error || 'Chưa huấn luyện hoặc đang cập nhật dữ liệu...'}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {runJobSuccessMsg && (
        <div className="p-3.5 bg-green-950/40 border border-green-500/30 text-green-400 rounded-xl text-xs font-semibold flex items-center gap-2 animate-fade-in">
          <CheckCircle size={16} />
          {runJobSuccessMsg}
        </div>
      )}

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
                  <th className="px-6 py-4 w-32">Thao tác</th>
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
                    <td className="px-6 py-4">
                      <button
                        onClick={() => runJobMutation.mutate(job.id)}
                        disabled={runJobMutation.isPending && runJobMutation.variables === job.id}
                        className="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-550 text-white rounded text-[10px] font-bold shadow-sm transition flex items-center gap-1 cursor-pointer disabled:opacity-50"
                        title="Chạy ngay lập tức"
                      >
                        {runJobMutation.isPending && runJobMutation.variables === job.id ? (
                          <RefreshCw size={10} className="animate-spin" />
                        ) : (
                          <Play size={10} />
                        )}
                        Chạy ngay
                      </button>
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

      {/* 4. Crawler Logs Console */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-white/10 bg-slate-950/40 flex items-center justify-between">
          <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
            <Terminal size={14} className="text-green-500" />
            Nhật ký cào dữ liệu thời gian thực (Crawler Logs)
          </h3>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-[10px] text-green-400 font-semibold bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
              Live Tracking (10s)
            </div>
            <button
              onClick={() => refetchLogs()}
              className="p-1 border border-white/10 bg-slate-900/60 rounded text-slate-400 hover:bg-white/5 hover:text-white transition cursor-pointer text-xs flex items-center gap-1"
              title="Tải lại logs"
            >
              <RefreshCw size={12} />
              Tải lại
            </button>
          </div>
        </div>

        <div className="p-4 bg-slate-950/95 font-mono text-[11px] leading-relaxed text-slate-350 h-80 overflow-y-auto custom-scrollbar border-t border-white/5 space-y-1 select-text">
          {logsData?.logs && logsData.logs.length > 0 ? (
            logsData.logs.map((logLine, index) => {
              let lineClass = "text-slate-300";
              if (logLine.includes("[ERROR]")) {
                lineClass = "text-red-400 font-bold";
              } else if (logLine.includes("[WARNING]")) {
                lineClass = "text-amber-400 font-bold";
              } else if (logLine.includes("✅") || logLine.includes("success") || logLine.includes("OK")) {
                lineClass = "text-emerald-400";
              }
              return (
                <div key={`log-${index}`} className={`${lineClass} whitespace-pre-wrap`}>
                  {logLine}
                </div>
              );
            })
          ) : (
            <div className="text-slate-500 text-center py-10 italic">
              Không tìm thấy dòng log nào trong file logs/crawler.log hoặc hệ thống chưa bắt đầu cào.
            </div>
          )}
          <div ref={logEndRef} />
        </div>
        <div className="px-4 py-2 bg-slate-950 border-t border-white/5 text-[10px] text-slate-500 flex justify-between">
          <span>Tổng số dòng: {logsData?.total_lines ?? 0}</span>
          <span>Đang hiển thị {logsData?.returned_lines ?? 0} dòng cuối</span>
        </div>
      </div>
    </div>
  );
};

export default AdminScheduler;
