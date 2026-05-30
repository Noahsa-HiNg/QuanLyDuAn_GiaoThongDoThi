import { create } from 'zustand';
import type { RouteResult } from '../types/api.types';

interface MapState {
  fromPos: [number, number] | null; // [lat, lng]
  toPos: [number, number] | null;   // [lat, lng]
  fromName: string;
  toName: string;
  routeShortest: RouteResult | null;
  routeFastest: RouteResult | null;
  selectedMode: 'shortest' | 'fastest';
  
  setFromPos: (pos: [number, number] | null) => void;
  setToPos: (pos: [number, number] | null) => void;
  setFromName: (name: string) => void;
  setToName: (name: string) => void;
  setRouteShortest: (route: RouteResult | null) => void;
  setRouteFastest: (route: RouteResult | null) => void;
  setSelectedMode: (mode: 'shortest' | 'fastest') => void;
  clearRoute: () => void;
  resetAll: () => void;
}

export const useMapStore = create<MapState>((set) => ({
  fromPos: null,
  toPos: null,
  fromName: '',
  toName: '',
  routeShortest: null,
  routeFastest: null,
  selectedMode: 'shortest',

  setFromPos: (pos) => set({ fromPos: pos }),
  setToPos: (pos) => set({ toPos: pos }),
  setFromName: (name) => set({ fromName: name }),
  setToName: (name) => set({ toName: name }),
  setRouteShortest: (route) => set({ routeShortest: route }),
  setRouteFastest: (route) => set({ routeFastest: route }),
  setSelectedMode: (mode) => set({ selectedMode: mode }),
  clearRoute: () => set({ routeShortest: null, routeFastest: null }),
  resetAll: () => set({
    fromPos: null,
    toPos: null,
    fromName: '',
    toName: '',
    routeShortest: null,
    routeFastest: null,
    selectedMode: 'shortest',
  }),
}));
