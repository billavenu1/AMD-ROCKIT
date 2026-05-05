import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Cpu, Eye, X, Copy, Trash2, Send } from 'lucide-react';

interface DeploymentConfig {
  quantization: string;
  target_gpu: string;
}

interface Deployment {
  deployment_id: string;
  model_id: string;
  status: string;
  endpoint: string;
  api_key: string;
  config?: DeploymentConfig;
}

export const ActiveDeploymentsView: React.FC = () => {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selectedDeployment, setSelectedDeployment] = useState<Deployment | null>(null);

  useEffect(() => {
    fetch('http://localhost:5055/api/deployments')
      .then(res => res.json())
      .then(data => setDeployments(data))
      .catch(err => console.error("Failed to fetch deployments:", err));
  }, []);

  return (
    <div className="flex-1 flex bg-[#0A0A0A] overflow-hidden">
      {/* Main List */}
      <div className={`flex-1 flex flex-col transition-all duration-300 ${selectedDeployment ? 'pr-0' : ''}`}>
        <div className="p-8 pb-6">
          <h1 className="text-2xl font-bold text-white mb-2">Active Deployments</h1>
          <p className="text-gray-400 text-sm">Monitor and manage your deployed models.</p>
        </div>

        <div className="flex-1 p-8 pt-0 overflow-y-auto">
          <div className="bg-[#121212] border border-[#222] rounded-2xl overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#222]">
                  <th className="py-4 px-6 text-sm font-medium text-gray-400">Model</th>
                  <th className="py-4 px-6 text-sm font-medium text-gray-400">Status</th>
                  <th className="py-4 px-6 text-sm font-medium text-gray-400">Endpoint</th>
                  <th className="py-4 px-6 text-sm font-medium text-gray-400 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {deployments.map(dep => (
                  <tr key={dep.deployment_id} className="border-b border-[#222] hover:bg-[#1A1A1A]/50 transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-[#1A1A1A] rounded-lg">
                          {dep.model_id.includes('vl') ? <Eye className="w-5 h-5 text-[#60A5FA]" /> : <Cpu className="w-5 h-5 text-[#A78BFA]" />}
                        </div>
                        <span className="font-semibold text-white">{dep.model_id.replace('-', ' ').toUpperCase()}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${dep.status === 'Running' ? 'bg-[#34D399]' : 'bg-[#FBBF24]'}`}></span>
                        <span className={`text-sm font-medium ${dep.status === 'Running' ? 'text-[#34D399]' : 'text-[#FBBF24]'}`}>
                          {dep.status}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-sm text-gray-300 font-mono">
                      {dep.endpoint}
                    </td>
                    <td className="py-4 px-6 text-right">
                      <button 
                        onClick={() => setSelectedDeployment(dep)}
                        className="px-4 py-2 border border-[#8B5CF6]/30 text-[#A78BFA] hover:bg-[#8B5CF6]/10 rounded-lg text-sm font-medium transition-colors"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
                {deployments.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-gray-500 text-sm">
                      No active deployments found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Right Panel / Details */}
      <AnimatePresence>
        {selectedDeployment && (
          <motion.div 
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 400, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="border-l border-[#222] bg-[#121212] flex flex-col h-full shrink-0"
          >
            <div className="p-6 border-b border-[#222] flex justify-between items-center bg-[#0A0A0A]">
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-[#1A1A1A] rounded-lg">
                    {selectedDeployment.model_id.includes('vl') ? <Eye className="w-5 h-5 text-[#60A5FA]" /> : <Cpu className="w-5 h-5 text-[#A78BFA]" />}
                 </div>
                 <div>
                   <h2 className="font-bold text-white leading-tight">{selectedDeployment.model_id.replace('-', ' ').toUpperCase()} Details</h2>
                   <div className="flex items-center gap-1.5 mt-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${selectedDeployment.status === 'Running' ? 'bg-[#34D399]' : 'bg-[#FBBF24]'}`}></span>
                      <span className={`text-[10px] uppercase tracking-wider font-bold ${selectedDeployment.status === 'Running' ? 'text-[#34D399]' : 'text-[#FBBF24]'}`}>
                        {selectedDeployment.status}
                      </span>
                   </div>
                 </div>
              </div>
              <button onClick={() => setSelectedDeployment(null)} className="p-2 text-gray-500 hover:text-white rounded-lg hover:bg-[#1A1A1A] transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-8">
              {/* Connection Details */}
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">1. Connection Details</h3>
                  <p className="text-xs text-gray-400">Use the endpoint and API key to connect to your model.</p>
                </div>

                <div className="space-y-3">
                  <div className="bg-[#0A0A0A] border border-[#222] rounded-xl p-3 flex items-center justify-between group">
                    <div>
                      <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">Endpoint</div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#8B5CF6]/20 text-[#A78BFA]">POST</span>
                        <span className="text-sm text-gray-300 font-mono">{selectedDeployment.endpoint}</span>
                      </div>
                    </div>
                    <button className="text-gray-500 hover:text-[#A78BFA] transition-colors p-2">
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="bg-[#0A0A0A] border border-[#222] rounded-xl p-3 flex items-center justify-between group">
                    <div>
                      <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">API Key</div>
                      <div className="text-sm text-gray-300 font-mono">{selectedDeployment.api_key}</div>
                    </div>
                    <div className="flex gap-1">
                      <button className="text-gray-500 hover:text-white transition-colors p-2">
                        <Eye className="w-4 h-4" />
                      </button>
                      <button className="text-gray-500 hover:text-[#A78BFA] transition-colors p-2">
                        <Copy className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Try it out */}
              <div className="space-y-4 flex-1 flex flex-col h-64">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1">2. Try it out</h3>
                    <p className="text-xs text-gray-400">Send a message to your deployed model.</p>
                  </div>
                  <button className="text-xs flex items-center gap-1 text-gray-400 hover:text-white border border-[#222] px-2 py-1 rounded bg-[#0A0A0A]">
                    <Trash2 className="w-3 h-3" /> Clear chat
                  </button>
                </div>

                <div className="flex-1 bg-[#0A0A0A] border border-[#222] rounded-xl p-4 flex flex-col gap-4 overflow-y-auto">
                  {/* Sample Messages */}
                  <div className="flex flex-col gap-1 items-end">
                    <span className="text-[10px] text-[#A78BFA] font-bold px-2">You</span>
                    <div className="bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 text-gray-200 text-sm px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[85%]">
                      Explain the key features of {selectedDeployment.model_id.replace('-', ' ').toUpperCase()}.
                    </div>
                  </div>
                  
                  <div className="flex flex-col gap-1 items-start">
                    <span className="text-[10px] text-gray-500 font-bold px-2 flex items-center gap-1">
                      <Cpu className="w-3 h-3" /> Model
                    </span>
                    <div className="bg-[#1A1A1A] border border-[#222] text-gray-300 text-sm px-4 py-3 rounded-2xl rounded-tl-sm max-w-[95%] leading-relaxed">
                      I am a high-performance model. I excel in reasoning, generation, and multimodal tasks when deployed efficiently on AMD infrastructure.
                    </div>
                  </div>
                </div>

                <div className="relative mt-2">
                  <input 
                    type="text" 
                    placeholder="Enter a prompt..." 
                    className="w-full bg-[#0A0A0A] border border-[#222] rounded-xl pl-4 pr-12 py-3 text-sm text-white focus:outline-none focus:border-[#8B5CF6] transition-colors"
                  />
                  <button className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-[#8B5CF6] text-white rounded-lg hover:bg-[#7C3AED] transition-colors">
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
