export interface Project {
  id: string;
  name: string;
  description?: string;
  archived?: boolean;
  created: string;
  updated: string;
  source_count?: number;
  note_count?: number;
  chats?: ChatSession[];
}

export interface ChatSession {
  id: string;
  title: string;
  notebook_id?: string | null;
  model_override?: string | null;
  created: string;
  updated: string;
  message_count?: number;
}

export interface AssetModel {
  file_path?: string;
  url?: string;
}

export interface Source {
  id: string;
  title: string;
  topics?: string[];
  asset?: AssetModel;
  full_text?: string;
  embedded?: boolean;
  embedded_chunks?: number;
  insights_count?: number;
  status?: string;
  processing_info?: any;
  command_id?: string;
  created: string;
  updated: string;
  selected?: boolean;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  type: string;
}

export interface ChatMessage {
  id: string;
  type: 'human' | 'ai';
  content: string;
  created_at?: string;
}

export type RetrievalMode = 'Hybrid' | 'Vector' | 'Notebook';

export type View = 'dashboard' | 'elyra' | 'chat' | 'deploy' | 'models' | 'tools' | 'endpoints' | 'deployments' | 'vision';
