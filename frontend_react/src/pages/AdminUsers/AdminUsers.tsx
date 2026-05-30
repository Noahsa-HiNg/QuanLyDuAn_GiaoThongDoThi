import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersApi } from '../../api/users.api';
import { useAuthStore } from '../../store/authStore';
import { 
  Users, 
  UserPlus, 
  Lock, 
  Unlock, 
  Trash2, 
  X, 
  Mail, 
  UserCheck, 
  UserX
} from 'lucide-react';

const ROLE_BADGES = {
  admin: 'bg-red-500/10 text-red-400 border-red-500/20',
  csgt: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  user: 'bg-slate-800 text-slate-300 border-white/5',
};

const AdminUsers: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form states
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<'admin' | 'csgt' | 'user'>('user');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  // 1. Fetch Users
  const { data: users = [], isLoading } = useQuery({
    queryKey: ['adminUsers'],
    queryFn: () => usersApi.getUsers(),
  });

  // Mutations
  const createUserMutation = useMutation({
    mutationFn: (data: any) => usersApi.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
      setIsModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || 'Lỗi khi tạo người dùng mới.');
    },
  });

  const lockUserMutation = useMutation({
    mutationFn: (id: number) => usersApi.lockUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });

  const unlockUserMutation = useMutation({
    mutationFn: (id: number) => usersApi.unlockUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: (id: number) => usersApi.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
  });

  const resetForm = () => {
    setEmail('');
    setFullName('');
    setRole('user');
    setPassword('');
    setFormError(null);
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !fullName || !password) {
      setFormError('Vui lòng điền đầy đủ các thông tin bắt buộc.');
      return;
    }

    createUserMutation.mutate({
      email,
      full_name: fullName,
      role,
      password,
    });
  };

  const handleToggleLock = (user: any) => {
    if (user.id === currentUser?.id) return; // Prevent locking self
    if (user.is_locked) {
      unlockUserMutation.mutate(user.id);
    } else {
      lockUserMutation.mutate(user.id);
    }
  };

  const handleDeleteUser = (id: number) => {
    if (id === currentUser?.id) return; // Prevent deleting self
    if (window.confirm('Bạn có chắc chắn muốn xóa vĩnh viễn tài khoản người dùng này?')) {
      deleteUserMutation.mutate(id);
    }
  };

  return (
    <div className="min-h-screen pt-20 pb-10 px-4 md:px-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-white flex items-center gap-2">
            <Users className="text-blue-400" />
            Quản lý tài khoản người dùng
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Xem danh sách thành viên, khóa/mở khóa tài khoản cảnh sát giao thông hoặc cấp quyền quản trị hệ thống.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded-lg text-sm transition flex items-center gap-1.5 shadow-sm cursor-pointer self-start sm:self-auto"
        >
          <UserPlus size={16} /> Thêm tài khoản
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-400 animate-pulse text-sm">
            Đang tải danh sách người dùng...
          </div>
        ) : users.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950/80 border-b border-white/10 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-4 w-16">ID</th>
                  <th className="px-6 py-4">Họ và tên</th>
                  <th className="px-6 py-4">Email đăng nhập</th>
                  <th className="px-6 py-4">Chức vụ / Vai trò</th>
                  <th className="px-6 py-4">Trạng thái khóa</th>
                  <th className="px-6 py-4 w-40 text-center">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {users.map((u) => {
                  const isSelf = u.id === currentUser?.id;
                  const roleBadge = ROLE_BADGES[u.role as keyof typeof ROLE_BADGES] || ROLE_BADGES.user;

                  return (
                    <tr key={`user-row-${u.id}`} className="hover:bg-white/5 transition">
                      <td className="px-6 py-4 text-xs font-bold text-slate-500">#{u.id}</td>
                      <td className="px-6 py-4">
                        <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                          {u.full_name}
                          {isSelf && (
                            <span className="text-[9px] font-semibold bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded-full border border-white/5">
                              Bạn
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-400">
                        <span className="flex items-center gap-1">
                          <Mail size={12} className="text-slate-500" />
                          {u.email}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${roleBadge}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-[10px] font-bold ${
                          u.is_locked 
                            ? 'bg-red-500/10 text-red-400 border-red-500/20' 
                            : 'bg-green-500/10 text-green-400 border-green-500/20'
                        }`}>
                          {u.is_locked ? <UserX size={10} /> : <UserCheck size={10} />}
                          {u.is_locked ? 'Đang khóa' : 'Hoạt động'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center flex items-center justify-center gap-2">
                        {/* Lock / Unlock Toggle button */}
                        <button
                          onClick={() => handleToggleLock(u)}
                          disabled={isSelf}
                          className={`p-1.5 rounded-lg border transition ${
                            isSelf 
                              ? 'text-slate-600 border-white/5 cursor-not-allowed' 
                              : u.is_locked 
                                ? 'text-green-400 border-green-500/30 bg-green-500/10 hover:bg-green-500/20 cursor-pointer' 
                                : 'text-amber-400 border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 cursor-pointer'
                          }`}
                          title={u.is_locked ? 'Mở khóa tài khoản' : 'Khóa tài khoản'}
                        >
                          {u.is_locked ? <Unlock size={14} /> : <Lock size={14} />}
                        </button>

                        {/* Delete user button */}
                        <button
                          onClick={() => handleDeleteUser(u.id)}
                          disabled={isSelf}
                          className={`p-1.5 rounded-lg border transition ${
                            isSelf 
                              ? 'text-slate-600 border-white/5 cursor-not-allowed' 
                              : 'text-red-400 border-red-500/30 bg-red-500/10 hover:bg-red-500/20 cursor-pointer'
                          }`}
                          title="Xóa tài khoản"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center text-slate-400 text-xs">
            Không tìm thấy tài khoản người dùng nào.
          </div>
        )}
      </div>

      {/* 4. Create User Modal Overlay */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-[1000] p-4 animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden text-white">
            {/* Header */}
            <div className="bg-slate-950/60 border-b border-white/10 px-5 py-4 flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
                <UserPlus className="text-blue-400" size={18} />
                Thêm tài khoản thành viên mới
              </h4>
              <button
                onClick={() => {
                  setIsModalOpen(false);
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

              {/* Full name */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Họ và tên
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nhập họ và tên đầy đủ..."
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>

              {/* Email */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Email đăng ký
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@domain.com"
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>

              {/* Password */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Mật khẩu đăng nhập
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu..."
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                  minLength={6}
                />
              </div>

              {/* Role selection */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                  Quyền hạn vai trò
                </label>
                <select
                  value={role}
                  onChange={(e: any) => setRole(e.target.value)}
                  className="w-full bg-slate-950/60 text-slate-200 border border-white/10 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="user">User (Thành viên cộng đồng)</option>
                  <option value="csgt">CSGT (Điều phối giao thông)</option>
                  <option value="admin">Admin (Quản trị hệ thống)</option>
                </select>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex justify-end gap-2 border-t border-white/10 mt-4">
                <button
                  type="button"
                  onClick={() => {
                    setIsModalOpen(false);
                    resetForm();
                  }}
                  className="px-4 py-2 border border-white/10 rounded-lg text-xs font-semibold text-slate-400 hover:bg-white/5 transition cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createUserMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-sm transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {createUserMutation.isPending ? 'Đang tạo...' : 'Tạo tài khoản'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminUsers;
