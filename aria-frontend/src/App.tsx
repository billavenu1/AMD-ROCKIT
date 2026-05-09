import React, { useState } from 'react';
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
    </div>
  );
}
