import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Search, 
  ChevronDown, 
  SquarePen, 
  Plus,
  Settings,
  PanelRight,
  MoreHorizontal,
  Pencil,
  Trash2
} from 'lucide-react';
import { useNotebooks, useCreateNotebook, useDeleteNotebook, useUpdateNotebook } from '../../hooks/useNotebooks';
import { useChatSessions, useCreateSession, useUpdateSession, useDeleteSession } from '../../hooks/useChat';
import { useGenUISessions, useCreateGenUISession, useDeleteGenUISession } from '../../hooks/useGenUIChat';
import { ConfirmDialog } from '../ui/ConfirmDialog';
import type { ChatSession } from '../../types';

interface SidebarProps {
  isSidebarCollapsed: boolean;
  activeProjectId: string | null;
  setActiveProjectId: (id: string | null) => void;
  activeChatId: string | null;
  setActiveChatId: (id: string | null) => void;
  isRightPanelOpen: boolean;
  setIsRightPanelOpen: (open: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isSidebarCollapsed,
  activeProjectId,
  setActiveProjectId,
  activeChatId,
  setActiveChatId,
  isRightPanelOpen,
  setIsRightPanelOpen,
}) => {
  const { data: projects = [] } = useNotebooks();
  const { data: allSessions = [] } = useChatSessions(null);
  const { data: genUISessions = [] } = useGenUISessions();
  const createNotebookMutation = useCreateNotebook();
  const deleteNotebookMutation = useDeleteNotebook();
  const updateNotebookMutation = useUpdateNotebook();
  const updateSessionMutation = useUpdateSession();
  const deleteSessionMutation = useDeleteSession();
  const createSessionMutation = useCreateSession();
  const createGenUISessionMutation = useCreateGenUISession();
  const deleteGenUISessionMutation = useDeleteGenUISession();
  
  const [isProjectsExpanded, setIsProjectsExpanded] = useState(true);
  const [isChatsExpanded, setIsChatsExpanded] = useState(true);
  const [expandedProjectIds, setExpandedProjectIds] = useState<string[]>([]);
  const [openProjectMenuId, setOpenProjectMenuId] = useState<string | null>(null);
  const [openChatMenuId, setOpenChatMenuId] = useState<string | null>(null);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);

  React.useEffect(() => {
    if (projects.length > 0 && expandedProjectIds.length === 0) {
      setExpandedProjectIds([projects[0].id]);
    }
  }, [projects, expandedProjectIds.length]);

  const handleCreateProject = () => {
    const name = prompt("Enter project name:", "New Project");
    if (name) createNotebookMutation.mutate({ name });
  };

  const handleNewChat = () => {
    setActiveProjectId(null);
    setIsChatsExpanded(true);
    createGenUISessionMutation.mutate(undefined, {
      onSuccess: (session) => setActiveChatId(session.id),
    });
  };

  const toggleProject = (projectId: string) => {
    setActiveProjectId(projectId);
    setActiveChatId(null);
    setExpandedProjectIds((prev) =>
      prev.includes(projectId) ? prev.filter((id) => id !== projectId) : [...prev, projectId]
    );
  };

  const handleCreateProjectChat = (projectId: string) => {
    setActiveProjectId(projectId);
    createSessionMutation.mutate({ notebookId: projectId }, {
      onSuccess: (session) => setActiveChatId(session.id),
    });
  };

  const handleRenameProject = (projectId: string, currentName: string) => {
    const name = prompt('Rename project:', currentName);
    if (name && name.trim() && name.trim() !== currentName) {
      updateNotebookMutation.mutate({ id: projectId, data: { name: name.trim() } });
    }
    setOpenProjectMenuId(null);
  };

  const handleRenameChat = (sessionId: string, currentTitle: string) => {
    const title = prompt('Rename chat:', currentTitle);
    if (title && title.trim() && title.trim() !== currentTitle) {
      updateSessionMutation.mutate({ sessionId, title: title.trim() });
    }
    setOpenChatMenuId(null);
  };

  const independentChats = genUISessions;
  const projectChats = (projectId: string) => allSessions.filter((chat) => chat.notebook_id === projectId);

  const renderChatRow = (chat: any, projectId: string | null) => (
    <div key={chat.id} className="relative group">
      <div
        className={`flex items-center gap-1 rounded-lg transition-all ${
          activeChatId === chat.id ? 'bg-[#1A1A1A] text-[#8B5CF6]' : 'text-gray-500 hover:text-gray-300 hover:bg-[#1A1A1A]/40'
        }`}
      >
        <button
          onClick={() => { setActiveProjectId(projectId); setActiveChatId(chat.id); }}
          className="w-full truncate px-3 py-1.5 text-left text-[13px]"
        >
          {chat.title}
        </button>
        <button
          onClick={(event) => {
            event.stopPropagation();
            setOpenProjectMenuId(null);
            setOpenChatMenuId(openChatMenuId === chat.id ? null : chat.id);
          }}
          className="mr-1 rounded-md p-1 text-gray-500 hover:bg-[#2A2A2A] hover:text-white"
          aria-label="Chat options"
          title="Chat options"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
      </div>

      {openChatMenuId === chat.id && (
        <div className="absolute right-1 top-8 z-[100] w-36 rounded-xl border border-[#333] bg-[#1F1F1F] p-1 shadow-2xl">
          <button
            onClick={() => handleRenameChat(chat.id, chat.title)}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-gray-300 hover:bg-[#2A2A2A] hover:text-white"
          >
            <Pencil className="h-3.5 w-3.5" /> Rename
          </button>
          <button
            onClick={() => { setDeletingChatId(chat.id); setOpenChatMenuId(null); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-red-400 hover:bg-red-500/10 hover:text-red-300"
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        </div>
      )}
    </div>
  );

  return (
    <motion.aside 
      initial={false}
      animate={{ width: isSidebarCollapsed ? 0 : 260, opacity: isSidebarCollapsed ? 0 : 1 }}
      className="flex flex-col bg-[#0F0F0F] border-r border-[#1F1F1F] h-full overflow-visible relative"
    >
      <div className="p-3 flex flex-col h-full">
        {/* Main Actions */}
        <div className="space-y-1 mb-6 pt-1">
          <button 
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-3 py-2.5 bg-[#1A1A1A] hover:bg-[#222] border border-[#333]/30 text-white rounded-xl transition-all group"
          >
            <SquarePen className="w-4 h-4 text-gray-400 group-hover:text-white" />
            <span className="text-sm font-medium">New chat</span>
          </button>
          
          <button className="w-full flex items-center gap-3 px-3 py-2 text-gray-400 hover:text-white hover:bg-[#1A1A1A]/50 rounded-lg transition-all">
            <Search className="w-4 h-4" />
            <span className="text-sm">Search chats</span>
          </button>
        </div>

        {/* Sections */}
        <div className="flex-1 overflow-y-auto -mx-2 px-2 space-y-4 custom-scrollbar">
          {/* PROJECTS */}
          <div className="space-y-1">
            <button 
              onClick={() => setIsProjectsExpanded(!isProjectsExpanded)}
              className="w-full flex items-center justify-between px-2 py-2 text-white hover:bg-[#1A1A1A]/30 rounded-lg group"
            >
              <span className="text-[13px] font-bold">Projects</span>
              <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isProjectsExpanded ? '' : '-rotate-90'}`} />
            </button>
            
            <AnimatePresence>
              {isProjectsExpanded && (
                <motion.div 
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="space-y-0.5 overflow-hidden"
                >
                  {projects.map((project) => (
                    <div key={project.id} className="relative">
                      <div
                        className={`group flex items-center gap-1 rounded-lg transition-all ${
                          activeProjectId === project.id ? 'bg-[#1A1A1A] text-white' : 'text-gray-500 hover:text-gray-300 hover:bg-[#1A1A1A]/40'
                        }`}
                      >
                        <button
                          onClick={() => toggleProject(project.id)}
                          className="flex min-w-0 flex-1 items-center gap-2 px-3 py-2 text-left text-sm"
                        >
                          <ChevronDown className={`h-3.5 w-3.5 shrink-0 text-gray-500 transition-transform ${expandedProjectIds.includes(project.id) ? '' : '-rotate-90'}`} />
                          <span className="truncate">{project.name}</span>
                        </button>

                        <div className="flex shrink-0 items-center pr-1">
                          <button
                            onClick={() => { setActiveProjectId(project.id); setIsRightPanelOpen(true); }}
                            className="rounded-md p-1 text-gray-500 hover:bg-[#2A2A2A] hover:text-white"
                            title="Open project panel"
                          >
                            <PanelRight className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleCreateProjectChat(project.id)}
                            className="rounded-md p-1 text-gray-500 hover:bg-[#2A2A2A] hover:text-white"
                            title="New chat in project"
                          >
                            <SquarePen className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              setOpenChatMenuId(null);
                              setOpenProjectMenuId(openProjectMenuId === project.id ? null : project.id);
                            }}
                            className="rounded-md p-1 text-gray-500 hover:bg-[#2A2A2A] hover:text-white"
                            aria-label="Project options"
                            title="Project options"
                          >
                            <MoreHorizontal className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                        {openProjectMenuId === project.id && (
                        <div className="absolute right-1 top-8 z-[100] w-36 rounded-xl border border-[#333] bg-[#1F1F1F] p-1 shadow-2xl">
                          <button
                            onClick={() => handleRenameProject(project.id, project.name)}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-gray-300 hover:bg-[#2A2A2A] hover:text-white"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Rename
                          </button>
                          <button
                            onClick={() => { setDeletingProjectId(project.id); setOpenProjectMenuId(null); }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-red-400 hover:bg-red-500/10 hover:text-red-300"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </button>
                        </div>
                      )}

                      <AnimatePresence>
                        {expandedProjectIds.includes(project.id) && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="ml-6 mt-1 space-y-0.5 overflow-visible"
                          >
                            {projectChats(project.id).length > 0 ? (
                              projectChats(project.id).map((chat) => renderChatRow(chat, project.id))
                            ) : (
                              <div className="px-3 py-1.5 text-[12px] text-gray-600">No project chats yet</div>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ))}
                  <button onClick={handleCreateProject} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-500 hover:text-white transition-all">
                    <Plus className="w-3 h-3" /> Create Project
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="space-y-1">
            <div className="group flex items-center justify-between rounded-lg px-2 py-2 text-white hover:bg-[#1A1A1A]/30">
              <button
                onClick={() => setIsChatsExpanded(!isChatsExpanded)}
                className="flex min-w-0 flex-1 items-center text-left"
              >
                <span className="text-[13px] font-bold">Chats</span>
              </button>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleNewChat}
                  className="rounded-md p-1 text-gray-500 opacity-80 transition-all hover:bg-[#2A2A2A] hover:text-white group-hover:opacity-100"
                  aria-label="New chat"
                  title="New chat"
                >
                  <SquarePen className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setIsChatsExpanded(!isChatsExpanded)}
                  className="rounded-md p-0.5 text-gray-500 hover:bg-[#2A2A2A] hover:text-white"
                  aria-label={isChatsExpanded ? 'Collapse chats' : 'Expand chats'}
                  title={isChatsExpanded ? 'Collapse chats' : 'Expand chats'}
                >
                  <ChevronDown className={`w-4 h-4 transition-transform ${isChatsExpanded ? '' : '-rotate-90'}`} />
                </button>
              </div>
            </div>

            <AnimatePresence>
              {isChatsExpanded && (
                <motion.div 
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="space-y-0.5 overflow-visible"
                >
                  {independentChats.length > 0 ? independentChats.map((chat) => renderChatRow(chat, null)) : (
                    <div className="px-3 py-2 text-[12px] text-gray-600">No independent chats yet</div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* BOTTOM SIDEBAR */}
        <div className="pt-4 border-t border-[#1F1F1F] flex flex-col gap-3">
          <div className="flex items-center justify-between px-2 mt-1">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#8B5CF6] to-[#EC4899] flex items-center justify-center text-[10px] font-bold text-white shadow-lg">
                VG
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-medium text-white">Venu Gopal</span>
              </div>
            </div>
            <button className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-[#1A1A1A] rounded-md transition-all">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={!!deletingProjectId}
        title="Delete Project"
        message="Are you sure you want to delete this project?"
        confirmLabel="Delete"
        onConfirm={() => {
          if (deletingProjectId) {
            deleteNotebookMutation.mutate(deletingProjectId);
            if (activeProjectId === deletingProjectId) setActiveProjectId(null);
          }
          setDeletingProjectId(null);
        }}
        onCancel={() => setDeletingProjectId(null)}
      />
      <ConfirmDialog
        isOpen={!!deletingChatId}
        title="Delete Chat"
        message="Are you sure you want to delete this chat?"
        confirmLabel="Delete"
        onConfirm={() => {
          if (deletingChatId) {
            // Check if it is a GenUI session
            if (deletingChatId.startsWith('genui_session:')) {
              deleteGenUISessionMutation.mutate(deletingChatId);
            } else {
              deleteSessionMutation.mutate({ sessionId: deletingChatId });
            }
            if (activeChatId === deletingChatId) setActiveChatId(null);
          }
          setDeletingChatId(null);
        }}
        onCancel={() => setDeletingChatId(null)}
      />
    </motion.aside>
  );
};
