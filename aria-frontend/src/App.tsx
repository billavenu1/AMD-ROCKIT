import React, { useState } from 'react';
import { MessageSquareHeart } from 'lucide-react';
import { NavBar } from './components/layout/NavBar';
import { Sidebar } from './components/layout/Sidebar';
import { RightPanel } from './components/layout/RightPanel';
import { ChatView } from './components/chat/ChatView';
import { GenUIChatView } from './components/chat/GenUIChatView';
import { DeployAgentsView } from './components/deploy/DeployAgentsView';
import { ElyraView } from './components/elyra/ElyraView';
import { ModelCatalogView } from './components/models/ModelCatalogView';
import { ActiveDeploymentsView } from './components/deployments/ActiveDeploymentsView';
import { VisionView } from './components/vision/VisionView';
import { DashboardView } from './components/dashboard/DashboardView';
import { View } from './types';

const FEEDBACK_URL = 'https://forms.gle/Cza63xPCqrJAjCHD6';

export default function App() {
  // Navigation State
  const [currentView, setCurrentView] = useState<View>('chat');
  const [isNavHovered, setIsNavHovered] = useState(false);
  
  // Sidebar States
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  
  // Right Panel / Context State
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  return (
    <div className="flex h-screen bg-[#0A0A0A] font-sans text-gray-300 overflow-hidden">
      {/* LEFTMOST ICON NAVIGATION BAR */}
      <NavBar 
        currentView={currentView}
        setCurrentView={setCurrentView}
        isNavHovered={isNavHovered}
        setIsNavHovered={setIsNavHovered}
      />

      {currentView === 'chat' ? (
        <div className="flex flex-1 h-full overflow-hidden relative">
          {/* LEFT SIDEBAR */}
          <Sidebar 
            isSidebarCollapsed={isSidebarCollapsed}
            activeProjectId={activeProjectId}
            setActiveProjectId={setActiveProjectId}
            activeChatId={activeChatId}
            setActiveChatId={setActiveChatId}
            isRightPanelOpen={isRightPanelOpen}
            setIsRightPanelOpen={setIsRightPanelOpen}
          />

          {/* CENTER - CHAT CANVAS (includes its own header) */}
          {activeProjectId ? (
            <ChatView
              isSidebarCollapsed={isSidebarCollapsed}
              setIsSidebarCollapsed={setIsSidebarCollapsed}
              activeProjectId={activeProjectId}
              activeChatId={activeChatId}
              setActiveChatId={setActiveChatId}
              selectedDocIds={selectedDocIds}
              isRightPanelOpen={isRightPanelOpen}
              setIsRightPanelOpen={setIsRightPanelOpen}
            />
          ) : (
            <GenUIChatView activeChatId={activeChatId} setActiveChatId={setActiveChatId} />
          )}

          {/* RIGHT PANEL - only when a project is active */}
          {activeProjectId && (
            <RightPanel 
              isRightPanelOpen={isRightPanelOpen}
              setIsRightPanelOpen={setIsRightPanelOpen}
              activeProjectId={activeProjectId}
              selectedDocIds={selectedDocIds}
              setSelectedDocIds={setSelectedDocIds}
            />
          )}
        </div>
      ) : currentView === 'dashboard' ? (
        <DashboardView />
      ) : currentView === 'elyra' ? (
        <ElyraView />
      ) : currentView === 'deploy' ? (
        <DeployAgentsView />
      ) : currentView === 'models' ? (
        <ModelCatalogView />
      ) : currentView === 'deployments' ? (
        <ActiveDeploymentsView />
      ) : currentView === 'vision' ? (
        <VisionView />
      ) : (
        <div className="flex-1 flex items-center justify-center bg-[#0A0A0A] text-gray-700 text-sm italic font-medium uppercase tracking-[0.2em]">
          Coming Soon: {currentView}
        </div>
      )}

      {/* Global Feedback Widget - always visible, bottom-right */}
      <a
        href={FEEDBACK_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-5 right-5 z-[9999] flex items-center gap-2.5 px-5 py-3 bg-gradient-to-r from-[#1A1A1A]/95 to-[#1F1F2E]/95 backdrop-blur-md border border-[#8B5CF6]/40 rounded-full shadow-xl shadow-purple-500/15 hover:border-[#8B5CF6]/70 hover:shadow-purple-500/30 hover:scale-105 transition-all group cursor-pointer"
        title="Leave a review"
      >
        <MessageSquareHeart className="w-5 h-5 text-[#A78BFA] group-hover:scale-110 transition-transform" />
        <span className="text-sm font-semibold text-gray-300 group-hover:text-white transition-colors">Feedback</span>
      </a>
    </div>
  );
}
