import { create } from 'zustand'

export const useAppStore = create((set) => ({
  // 편의점 필터
  cvsStore: null,
  cvsCategory: null,
  cvsEventType: null,
  setCvsStore: (store) => set({ cvsStore: store }),
  setCvsCategory: (cat) => set({ cvsCategory: cat }),
  setCvsEventType: (et) => set({ cvsEventType: et }),

  // 올리브영 필터
  oyCategory: null,
  oySort: 'discount',
  setOyCategory: (cat) => set({ oyCategory: cat }),
  setOySort: (sort) => set({ oySort: sort }),

  // 다이소 필터
  daisoCategory: null,
  daisoPrice: null,
  daisoSort: 'score',
  setDaisoCategory: (cat) => set({ daisoCategory: cat }),
  setDaisoPrice: (p) => set({ daisoPrice: p }),
  setDaisoSort: (sort) => set({ daisoSort: sort }),

  // 핫딜 필터
  hotdealSort: 'votes',
  hotdealCategory: null,
  setHotdealSort: (sort) => set({ hotdealSort: sort }),
  setHotdealCategory: (cat) => set({ hotdealCategory: cat }),
}))
