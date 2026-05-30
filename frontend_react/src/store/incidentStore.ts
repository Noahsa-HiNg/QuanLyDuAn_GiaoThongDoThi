import { create } from 'zustand';

interface IncidentFilters {
  type: string;
  status: string;
  isActive: boolean | null;
}

interface IncidentState {
  selectedIncidentIds: number[];
  filters: IncidentFilters;
  
  toggleSelectIncident: (id: number) => void;
  selectAllIncidents: (ids: number[]) => void;
  clearSelection: () => void;
  
  setFilter: <K extends keyof IncidentFilters>(key: K, value: IncidentFilters[K]) => void;
  resetFilters: () => void;
}

export const useIncidentStore = create<IncidentState>((set) => ({
  selectedIncidentIds: [],
  filters: {
    type: 'all',
    status: 'all',
    isActive: null,
  },

  toggleSelectIncident: (id) => set((state) => {
    const isSelected = state.selectedIncidentIds.includes(id);
    return {
      selectedIncidentIds: isSelected
        ? state.selectedIncidentIds.filter((x) => x !== id)
        : [...state.selectedIncidentIds, id],
    };
  }),

  selectAllIncidents: (ids) => set({ selectedIncidentIds: ids }),
  clearSelection: () => set({ selectedIncidentIds: [] }),

  setFilter: (key, value) => set((state) => ({
    filters: {
      ...state.filters,
      [key]: value,
    },
  })),

  resetFilters: () => set({
    filters: {
      type: 'all',
      status: 'all',
      isActive: null,
    },
  }),
}));
