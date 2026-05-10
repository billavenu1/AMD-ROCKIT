import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api/client';
import { Source } from '../types';

export function useSources(notebookId: string | null) {
  return useQuery<Source[]>({
    queryKey: ['sources', notebookId],
    queryFn: async () => {
      const response = await api.get(`/sources?notebook_id=${notebookId}`);
      return response.data;
    },
    enabled: !!notebookId,
    refetchInterval: 10000, // Poll every 10s to catch async processing updates
  });
}

export function useUploadSource(notebookId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('type', 'upload');
      if (notebookId) {
        formData.append('notebooks', JSON.stringify([notebookId]));
      }
      formData.append('file', file);
      formData.append('title', file.name);
      formData.append('async_processing', 'false');
      const response = await api.post('/sources', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', notebookId] });
    },
    onError: (error) => {
      console.error('Upload failed:', error);
    },
  });
}

/** Upload multiple files sequentially */
export function useUploadMultipleSources(notebookId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const results = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append('type', 'upload');
        if (notebookId) {
          formData.append('notebooks', JSON.stringify([notebookId]));
        }
        formData.append('file', file);
        formData.append('title', file.name);
        formData.append('async_processing', 'false');
        const response = await api.post('/sources', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        results.push(response.data);
      }
      return results;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', notebookId] });
    },
    onError: (error) => {
      console.error('Multi-upload failed:', error);
    },
  });
}

export function useAddLinkSource(notebookId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (url: string) => {
      const formData = new FormData();
      formData.append('type', 'link');
      if (notebookId) {
        formData.append('notebooks', JSON.stringify([notebookId]));
      }
      formData.append('url', url);
      formData.append('title', url);
      formData.append('async_processing', 'false');
      const response = await api.post('/sources', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', notebookId] });
    },
    onError: (error) => {
      console.error('Add link failed:', error);
    },
  });
}

export function useDeleteSource(notebookId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: string) => {
      await api.delete(`/sources/${sourceId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', notebookId] });
    },
    onError: (error) => {
      console.error('Delete source failed:', error);
    },
  });
}
