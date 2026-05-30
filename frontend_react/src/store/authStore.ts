import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types/api.types';

interface AuthState {
  token: string | null;
  user: User | null;
  isLoggedIn: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isLoggedIn: false,
      login: (token, user) => set({ token, user, isLoggedIn: true }),
      logout: () => set({ token: null, user: null, isLoggedIn: false }),
    }),
    {
      name: 'auth-storage',
    }
  )
);
