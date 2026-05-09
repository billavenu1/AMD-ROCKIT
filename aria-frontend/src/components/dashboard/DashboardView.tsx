import React, { useState, useEffect } from 'react';
import { Activity, Cpu, Server, HardDrive, Network, Layers } from 'lucide-react';

const API_BASE = 'http://localhost:5055';

export const DashboardView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'vllm' | 'system'>('vllm');
  const [vllmStats, setVllmStats] = useState<any[]>([]);
  const [systemStats, setSystemStats] = useState<any>(null);

  useEffect(() => {
    const fetchVllm = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/monitor/vllm`);
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();
        setVllmStats(data);
      } catch (e) {
        console.error("Failed to fetch vLLM stats", e);
      }
    };

    const fetchSystem = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/monitor/system`);
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();
        setSystemStats(data);
      } catch (e) {
        console.error("Failed to fetch System stats", e);
      }
    };

    // Initial fetch
    if (activeTab === 'vllm') {
      fetchVllm();
    } else {
      fetchSystem();
    }

    // Polling every 5 seconds
    const interval = setInterval(() => {
      if (activeTab === 'vllm') {
        fetchVllm();
      } else {
        fetchSystem();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [activeTab]);

  return (
    <div className="flex-1 flex flex-col bg-[#0A0A0A] overflow-hidden">
      {/* Header */}
      <div className="p-8 pb-4 border-b border-[#1A1A1A]">
        <div className="flex items-center gap-3 mb-6">
          <Activity className="w-6 h-6 text-[#A78BFA]" />
          <h1 className="text-2xl font-bold text-white">ARIA Monitor</h1>
        </div>

        {/* Tabs */}
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab('vllm')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'vllm'
                ? 'bg-[#8B5CF6]/20 text-[#A78BFA] border border-[#8B5CF6]/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
            }`}
          >
            vLLM Models
          </button>
          <button
            onClick={() => setActiveTab('system')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'system'
                ? 'bg-[#8B5CF6]/20 text-[#A78BFA] border border-[#8B5CF6]/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
            }`}
          >
            System Resources
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-8 overflow-y-auto">
        {activeTab === 'vllm' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {vllmStats.length === 0 ? (
              <div className="text-gray-500 text-sm">Loading vLLM stats...</div>
            ) : (
              vllmStats.map((model, idx) => (
                <div key={idx} className="bg-[#121212] border border-[#222] rounded-2xl p-6">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-bold text-white">{model.name}</h3>
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${model.status === 'up' ? 'bg-emerald-400' : 'bg-red-400'}`} />
                      <span className={`text-xs font-bold uppercase tracking-wider ${model.status === 'up' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {model.status}
                      </span>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-400">VRAM Usage</span>
                        <span className="text-gray-200">{model.vram_pct}%</span>
                      </div>
                      <div className="w-full h-2 bg-[#1A1A1A] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
                          style={{ width: `${model.vram_pct}%` }}
                        />
                      </div>
                    </div>
                    
                    <div className="flex justify-between items-center py-2 border-t border-[#1A1A1A]">
                      <span className="text-sm text-gray-400">Active Requests</span>
                      <span className="text-sm font-bold text-white">{model.active}</span>
                    </div>
                    
                    <div className="flex justify-between items-center py-2 border-t border-[#1A1A1A]">
                      <span className="text-sm text-gray-400">Queued Requests</span>
                      <span className="text-sm font-bold text-white">{model.queued}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {!systemStats ? (
              <div className="text-gray-500 text-sm">Loading System stats...</div>
            ) : (
              <>
                {/* CPU */}
                <div className="bg-[#121212] border border-[#222] rounded-2xl p-6">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-[#1A1A1A] rounded-lg">
                      <Cpu className="w-5 h-5 text-blue-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white">CPU</h3>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Usage</span>
                        <span className="text-gray-200 font-bold">{systemStats.cpu.usage_pct}%</span>
                      </div>
                      <div className="w-full h-3 bg-[#1A1A1A] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${systemStats.cpu.usage_pct}%` }}
                        />
                      </div>
                    </div>
                    <div className="pt-2 text-sm text-gray-400">
                      {systemStats.cpu.cores} cores @ {(systemStats.cpu.freq_mhz / 1000).toFixed(1)} GHz
                    </div>
                  </div>
                </div>

                {/* Memory */}
                <div className="bg-[#121212] border border-[#222] rounded-2xl p-6">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-[#1A1A1A] rounded-lg">
                      <Server className="w-5 h-5 text-emerald-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white">Memory</h3>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Usage</span>
                        <span className="text-gray-200 font-bold">{systemStats.memory.used_gb} / {systemStats.memory.total_gb} GB</span>
                      </div>
                      <div className="w-full h-3 bg-[#1A1A1A] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-emerald-500 rounded-full"
                          style={{ width: `${systemStats.memory.pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* GPU */}
                <div className="bg-[#121212] border border-[#222] rounded-2xl p-6">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-[#1A1A1A] rounded-lg">
                      <Layers className="w-5 h-5 text-purple-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white">AMD GPU</h3>
                  </div>
                  <div className="space-y-4">
                    {systemStats.gpu.map((g: any, i: number) => (
                      <div key={i} className="space-y-3">
                        <div className="text-sm font-medium text-white">{g.name}</div>
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-gray-400">Utilization</span>
                          <span className="text-gray-200 font-bold">{g.util_pct}%</span>
                        </div>
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-gray-400">VRAM</span>
                          <span className="text-gray-200 font-bold">
                            {(g.vram_used / 1e9).toFixed(1)} / {(g.vram_total / 1e9).toFixed(1)} GB
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Network */}
                <div className="bg-[#121212] border border-[#222] rounded-2xl p-6">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-[#1A1A1A] rounded-lg">
                      <Network className="w-5 h-5 text-amber-400" />
                    </div>
                    <h3 className="text-lg font-bold text-white">Network</h3>
                  </div>
                  <div className="space-y-4 mt-2">
                    <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-xl border border-[#1A1A1A]">
                      <div className="flex items-center gap-3">
                        <div className="text-amber-400 text-xl">↑</div>
                        <span className="text-sm text-gray-400">Sent</span>
                      </div>
                      <span className="text-sm font-bold text-white">{systemStats.network.bytes_sent_mb} MB</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-xl border border-[#1A1A1A]">
                      <div className="flex items-center gap-3">
                        <div className="text-amber-400 text-xl">↓</div>
                        <span className="text-sm text-gray-400">Received</span>
                      </div>
                      <span className="text-sm font-bold text-white">{systemStats.network.bytes_recv_mb} MB</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
