import React from 'react';
import { motion } from 'motion/react';
import { 
  LayoutDashboard, 
  Workflow,
  MessageSquare, 
  Rocket, 
  BrainCircuit, 
  Puzzle, 
  Terminal, 
  Settings,
  Server,
  Eye
} from 'lucide-react';
import { View } from '../../types';

interface NavBarProps {
  currentView: View;
  setCurrentView: (view: View) => void;
  isNavHovered: boolean;
  setIsNavHovered: (hovered: boolean) => void;
}

export const NavBar: React.FC<NavBarProps> = ({ 
  currentView, 
  setCurrentView, 
  isNavHovered, 
  setIsNavHovered 
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'elyra', label: 'Elyra', icon: Workflow },
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'deploy', label: 'Deploy Agents', icon: Rocket },
    { id: 'models', label: 'Models', icon: BrainCircuit },
    { id: 'deployments', label: 'Deployments', icon: Server },
    { id: 'vision', label: 'Vision', icon: Eye },
    { id: 'tools', label: 'Tools', icon: Puzzle },
    { id: 'endpoints', label: 'Endpoints', icon: Terminal },
  ];

  return (
    <motion.nav 
      onMouseEnter={() => setIsNavHovered(true)}
      onMouseLeave={() => setIsNavHovered(false)}
      initial={false}
      animate={{ width: isNavHovered ? 200 : 64 }}
      className="h-full bg-[#080808] border-r border-[#161616] flex flex-col items-center py-4 z-[100] transition-all duration-300 shadow-[2px_0_10px_rgba(0,0,0,0.5)]"
    >
      <div className="flex flex-col gap-8 w-full px-3">
        {/* Logo */}
        <div className="flex items-center gap-3 px-1 ml-1.5 h-8 overflow-hidden">
          <div className={`w-7 h-7 bg-white rounded flex-shrink-0 flex items-center justify-center transition-all ${isNavHovered ? 'scale-100' : 'scale-90 opacity-80'}`}>
            <span className="text-black font-extrabold text-lg uppercase italic leading-none">A</span>
          </div>
          {isNavHovered && (
             <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-white font-bold tracking-tighter text-lg">ARIA</motion.span>
          )}
        </div>

        {/* Navigation Items */}
        <div className="flex flex-col gap-1 w-full">
          {navItems.map((item) => (
            <button 
              key={item.id}
              onClick={() => setCurrentView(item.id as View)}
              className={`flex items-center gap-4 px-2 py-2.5 rounded-xl transition-all relative group overflow-hidden ${
                currentView === item.id 
                ? 'bg-gradient-to-r from-[#8B5CF6]/20 to-transparent text-[#A78BFA] border border-[#8B5CF6]/30' 
                : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
              }`}
            >
              <div className="relative z-10 flex-shrink-0 ml-1">
                <item.icon className={`w-5 h-5 transition-transform group-hover:scale-110 ${currentView === item.id ? 'stroke-[2.5]' : ''}`} />
                {currentView === item.id && (
                  <motion.div layoutId="nav-indicator" className="absolute -left-3 top-0 w-1 h-5 bg-[#8B5CF6] rounded-r-full" />
                )}
              </div>
              {isNavHovered && (
                <motion.span 
                  initial={{ opacity: 0, x: -10 }} 
                  animate={{ opacity: 1, x: 0 }} 
                  className="text-[11px] font-bold uppercase tracking-widest whitespace-nowrap"
                >
                  {item.label}
                </motion.span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-auto w-full px-3 pb-2">
         <button className="flex items-center gap-4 px-2 py-3 rounded-xl text-gray-600 hover:text-gray-300 hover:bg-white/5 w-full transition-all group overflow-hidden">
           <div className="ml-1 flex-shrink-0">
             <Settings className="w-5 h-5 group-hover:rotate-45 transition-transform" />
           </div>
           {isNavHovered && (
             <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-[11px] font-bold uppercase tracking-widest whitespace-nowrap">Settings</motion.span>
           )}
         </button>
      </div>
    </motion.nav>
  );
};
