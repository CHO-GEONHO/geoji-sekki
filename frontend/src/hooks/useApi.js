import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── 피드 ──
export function useFeed(date) {
  return useQuery({
    queryKey: ['feed', date],
    queryFn: () => api.get('/feed', { params: date ? { date } : {} }).then(r => r.data),
  })
}

export function useFeedDates() {
  return useQuery({
    queryKey: ['feed-dates'],
    queryFn: () => api.get('/feed/dates').then(r => r.data),
  })
}

// ── 편의점 ──
export function useCvsProducts({ store, category, event_type, page = 1 } = {}) {
  return useQuery({
    queryKey: ['cvs', store, category, event_type, page],
    queryFn: () => api.get('/cvs', {
      params: { store, category, event_type, page, page_size: 50 },
    }).then(r => r.data),
  })
}

export function useCvsCompare(product) {
  return useQuery({
    queryKey: ['cvs-compare', product],
    queryFn: () => api.get('/cvs/compare', { params: { product } }).then(r => r.data),
    enabled: !!product,
  })
}

export function useCvsCategories() {
  return useQuery({
    queryKey: ['cvs-categories'],
    queryFn: () => api.get('/cvs/categories').then(r => r.data),
    staleTime: 60 * 60 * 1000,
  })
}

// ── 올리브영 ──
export function useOliveyoung({ category, event_type, sort = 'discount', page = 1 } = {}) {
  return useQuery({
    queryKey: ['oliveyoung', category, event_type, sort, page],
    queryFn: () => api.get('/oliveyoung', {
      params: { category, event_type, sort, page, page_size: 50 },
    }).then(r => r.data),
  })
}

export function useOyCalendar(year) {
  return useQuery({
    queryKey: ['oy-calendar', year],
    queryFn: () => api.get('/oliveyoung/calendar', { params: year ? { year } : {} }).then(r => r.data),
    staleTime: 24 * 60 * 60 * 1000,
  })
}

// ── 다이소 ──
export function useDaiso({ category, price, sort = 'score', page = 1 } = {}) {
  return useQuery({
    queryKey: ['daiso', category, price, sort, page],
    queryFn: () => api.get('/daiso', {
      params: { category, price, sort, page, page_size: 50 },
    }).then(r => r.data),
  })
}

export function useDaisoNew(page = 1) {
  return useQuery({
    queryKey: ['daiso-new', page],
    queryFn: () => api.get('/daiso/new', { params: { page, page_size: 50 } }).then(r => r.data),
  })
}

// ── 핫딜 ──
export function useHotdeals({ sort = 'votes', category, source, page = 1, limit = 20 } = {}) {
  return useQuery({
    queryKey: ['hotdeals', sort, category, source, page],
    queryFn: () => api.get('/hotdeals', {
      params: { sort, category, source, page, limit },
    }).then(r => r.data),
  })
}

// ── 쿠팡 ──
export function useCoupang({ category, sort = 'discount', page = 1 } = {}) {
  return useQuery({
    queryKey: ['coupang', category, sort, page],
    queryFn: () => api.get('/coupang', {
      params: { category, sort, page, page_size: 50 },
    }).then(r => r.data),
  })
}

// ── 헬스 ──
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then(r => r.data),
    staleTime: 30 * 1000,
  })
}
