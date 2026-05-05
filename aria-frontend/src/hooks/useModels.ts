import { useQuery } from '@tanstack/react-query';
import api from '../lib/api/client';
import { Model } from '../types';

export interface AvailableModel {
  id: string;
  name: string;
  provider: string;
  type: string;
}

export function useModels(type: string = 'language') {
  return useQuery<Model[]>({
    queryKey: ['models', type],
    queryFn: async () => {
      const response = await api.get(`/models?type=${type}`);
      return response.data;
    },
  });
}

export function useAvailableModels() {
  return useQuery<AvailableModel[]>({
    queryKey: ['availableModels'],
    queryFn: async () => {
      const response = await api.get('/catalog/available-models');
      return response.data;
    },
  });
}

export function useDefaultModels() {
  return useQuery({
    queryKey: ['models', 'defaults'],
    queryFn: async () => {
      // Assuming there's an endpoint or we get it from config
      const response = await api.get('/models/defaults');
      return response.data;
    },
  });
}
