import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Copy, Trash2, Send, Network, Loader2, Cpu, Eye, Database, Volume2, Plus, AlertTriangle, Server } from 'lucide-react';

const API_BASE = 'http://localhost:5055';

interface Workflow {
  workflow_id: string;
  name: string;
  status: string;
  endpoint: string | null;
  created_at: string;
  published_at: string | null;
  config: { model: string; instructions: string; knowledge: { type: string; source: string }; tools: string[] };
  metrics?: { total_invocations: number; avg_latency_ms: number };
}

interface VLLMDeployment {
  deployment_id: string;
  model_id: string;
  model_name: string;
  status: string;
  endpoint: string;
  port: number;
  api_key: string;
  config: Record<string, any>;
}

interface RegistryModel {
  id: string;
  name: string;
  type: string;
  description: string;
  vram_required: string;
  icon: string;
  deploy_options: { quantization: { label: string; value: string; vram_estimate: string }[]; target_gpu: string[] };
}

const typeIcon = (type: string) => {
  if (type === 'LLM') return <Cpu className="w-5 h-5 text-[#A78BFA]" />;
  if (type === 'Vision') return <Eye className="w-5 h-5 text-[#34D399]" />;
  if (type === 'Embedding') return <Database className="w-5 h-5 text-[#60A5FA]" />;
  if (type === 'TTS') return <Volume2 className="w-5 h-5 text-[#F472B6]" />;
  return <Server className="w-5 h-5 text-gray-400" />;
};

const statusColor = (s: string) => {
  const sl = s.toLowerCase();
  if (sl === 'running' || sl === 'up') return { dot: 'bg-[#34D399]', text: 'text-[#34D399]' };
  if (sl === 'starting') return { dot: 'bg-[#FBBF24]', text: 'text-[#FBBF24]' };
  if (sl === 'failed' || sl === 'down') return { dot: 'bg-red-500', text: 'text-red-400' };
  return { dot: 'bg-gray-500', text: 'text-gray-400' };
};

export const ActiveDeploymentsView: React.FC = () => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [vllmDeps, setVllmDeps] = useState<VLLMDeployment[]>([]);
  const [gpuEnabled, setGpuEnabled] = useState(false);
  const [registry, setRegistry] = useState<RegistryModel[]>([]);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deployingId, setDeployingId] = useState<string | null>(null);
  const [selectedQuant, setSelectedQuant] = useState<string>('');
  const [selectedGpu, setSelectedGpu] = useState<string>('');
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<{role: string; content: string}[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchAll = () => {
    fetch(`${API_BASE}/api/workflows`).then(r => r.json()).then(setWorkflows).catch(() => {});
    fetch(`${API_BASE}/api/deployments/`).then(r => r.json()).then(setVllmDeps).catch(() => {});
    fetch(`${API_BASE}/api/deployments/gpu-enabled`).then(r => r.json()).then(d => setGpuEnabled(d.gpu_enabled)).catch(() => {});
    fetch(`${API_BASE}/api/deployments/registry`).then(r => r.json()).then(setRegistry).catch(() => {});
  };

  useEffect(() => { fetchAll(); const id = setInterval(fetchAll, 15000); return () => clearInterval(id); }, []);

  const handleDeleteWorkflow = async (id: string) => {
    await fetch(`${API_BASE}/api/workflows/${id}`, { method: 'DELETE' });
    if (selected?.workflow_id === id) { setSelected(null); setChatMessages([]); }
    fetchAll();
  };

  const handleUndeploy = async (id: string) => {
    await fetch(`${API_BASE}/api/deployments/${id}`, { method: 'DELETE' });
    fetchAll();
  };

  const handleDeploy = async (model: RegistryModel) => {
    setDeployingId(model.id);
    try {
      await fetch(`${API_BASE}/api/deployments/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: model.id,
          model_name: model.name,
          quantization: selectedQuant || model.deploy_options.quantization[0]?.value,
          target_gpu: selectedGpu || model.deploy_options.target_gpu[0],
        }),
      });
      setShowDeployModal(false);
      fetchAll();
    } catch (e: any) {
      alert(`Deploy failed: ${e.message}`);
    } finally {
      setDeployingId(null);
    }
  };

  const handleCopy = (text: string) => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); };
  const handleSelect = (wf: Workflow) => { setSelected(wf); setChatMessages([]); setChatInput(''); };

  const handleChatSend = async () => {
    if (!chatInput.trim() || !selected?.endpoint) return;
    const msg = chatInput.trim(); setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: msg }]);
    setChatLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/workflows/${selected.workflow_id}/invoke`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }),
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      fetchAll();
    } catch (e: any) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally { setChatLoading(false); }
  };

  return (
    <div className="flex-1 flex bg-[#0A0A0A] overflow-hidden">
      <div className="flex-1 flex flex-col">
        <div className="p-8 pb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Active Deployments</h1>
            <p className="text-gray-400 text-sm">Manage deployed models and agentic workflows.</p>
          </div>
          <button onClick={() => setShowDeployModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#8B5CF6] to-[#6D28D9] text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity shadow-lg shadow-purple-500/20">
            <Plus className="w-4 h-4" /> Deploy Model
          </button>
        </div>

        {/* {!gpuEnabled && (
          <div className="mx-8 mb-4 flex items-center gap-3 bg-[#FBBF24]/10 border border-[#FBBF24]/20 rounded-xl px-4 py-3">
            <AlertTriangle className="w-5 h-5 text-[#FBBF24] shrink-0" />
            <span className="text-sm text-[#FBBF24]/90">GPU mode disabled. Set <code className="bg-black/30 px-1.5 py-0.5 rounded text-xs">USE_GPU=true</code> in .env to enable vLLM model deployment.</span>
          </div>
        )} */}

        <div className="flex-1 p-8 pt-0 overflow-y-auto space-y-6">
          {/* vLLM Model Deployments */}
          {vllmDeps.length > 0 && (
            <div>
              <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">Model Deployments (vLLM)</h2>
              <div className="bg-[#121212] border border-[#222] rounded-2xl overflow-hidden">
                <table className="w-full text-left border-collapse">
                  <thead><tr className="border-b border-[#222]">
                    <th className="py-3 px-5 text-xs font-medium text-gray-500">Model</th>
                    <th className="py-3 px-5 text-xs font-medium text-gray-500">Status</th>
                    <th className="py-3 px-5 text-xs font-medium text-gray-500">Endpoint</th>
                    <th className="py-3 px-5 text-xs font-medium text-gray-500">Config</th>
                    <th className="py-3 px-5 text-xs font-medium text-gray-500 text-right">Actions</th>
                  </tr></thead>
                  <tbody>
                    {vllmDeps.map(dep => { const sc = statusColor(dep.status); return (
                      <tr key={dep.deployment_id} className="border-b border-[#222] hover:bg-[#1A1A1A]/50 transition-colors">
                        <td className="py-3 px-5"><div className="flex items-center gap-3">
                          <div className="p-2 bg-[#1A1A1A] rounded-lg"><Cpu className="w-4 h-4 text-[#A78BFA]" /></div>
                          <div><span className="font-semibold text-white text-sm block">{dep.model_name || dep.model_id}</span>
                          <span className="text-[10px] text-gray-600 font-mono">{dep.deployment_id}</span></div>
                        </div></td>
                        <td className="py-3 px-5"><div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${sc.dot}`} /><span className={`text-xs font-medium capitalize ${sc.text}`}>{dep.status}</span>
                        </div></td>
                        <td className="py-3 px-5 text-xs text-gray-400 font-mono max-w-[180px] truncate">{dep.endpoint || '—'}</td>
                        <td className="py-3 px-5 text-xs text-gray-500">{dep.config?.quantization || '—'} / {dep.config?.target_gpu || '—'}</td>
                        <td className="py-3 px-5 text-right">
                          <button onClick={() => handleUndeploy(dep.deployment_id)} className="p-1.5 text-gray-600 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"><Trash2 className="w-4 h-4" /></button>
                        </td>
                      </tr>
                    );})}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Workflow Deployments */}
          <div>
            <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">Agentic Workflows</h2>
            <div className="bg-[#121212] border border-[#222] rounded-2xl overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead><tr className="border-b border-[#222]">
                  <th className="py-3 px-5 text-xs font-medium text-gray-500">Workflow</th>
                  <th className="py-3 px-5 text-xs font-medium text-gray-500">Model</th>
                  <th className="py-3 px-5 text-xs font-medium text-gray-500">Status</th>
                  <th className="py-3 px-5 text-xs font-medium text-gray-500">Endpoint</th>
                  <th className="py-3 px-5 text-xs font-medium text-gray-500">Invocations</th>
                  <th className="py-3 px-5 text-xs font-medium text-gray-500 text-right">Actions</th>
                </tr></thead>
                <tbody>
                  {workflows.map(wf => { const sc = statusColor(wf.status); return (
                    <tr key={wf.workflow_id} className="border-b border-[#222] hover:bg-[#1A1A1A]/50 transition-colors">
                      <td className="py-3 px-5"><div className="flex items-center gap-3">
                        <div className="p-2 bg-[#1A1A1A] rounded-lg"><Network className="w-4 h-4 text-[#A78BFA]" /></div>
                        <div><span className="font-semibold text-white text-sm block">{wf.name}</span>
                        <span className="text-[10px] text-gray-600 font-mono">{wf.workflow_id}</span></div>
                      </div></td>
                      <td className="py-3 px-5 text-sm text-gray-300">{wf.config.model}</td>
                      <td className="py-3 px-5"><div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${sc.dot}`} /><span className={`text-xs font-medium capitalize ${sc.text}`}>{wf.status}</span>
                      </div></td>
                      <td className="py-3 px-5 text-xs text-gray-400 font-mono max-w-[180px] truncate">{wf.endpoint || '—'}</td>
                      <td className="py-3 px-5 text-sm text-gray-300">{wf.metrics?.total_invocations ?? 0}</td>
                      <td className="py-3 px-5 text-right"><div className="flex items-center justify-end gap-2">
                        <button onClick={() => handleSelect(wf)} className="px-3 py-1 border border-[#8B5CF6]/30 text-[#A78BFA] hover:bg-[#8B5CF6]/10 rounded-lg text-xs font-medium transition-colors">View</button>
                        <button onClick={() => handleDeleteWorkflow(wf.workflow_id)} className="p-1.5 text-gray-600 hover:text-red-400 rounded-lg hover:bg-red-500/10 transition-colors"><Trash2 className="w-4 h-4" /></button>
                      </div></td>
                    </tr>
                  );})}
                  {workflows.length === 0 && vllmDeps.length === 0 && (
                    <tr><td colSpan={6} className="py-8 text-center text-gray-500 text-sm">No deployments yet. Click "Deploy Model" to get started.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Workflow Details */}
      <AnimatePresence>
        {selected && (
          <motion.div initial={{ width: 0, opacity: 0 }} animate={{ width: 420, opacity: 1 }} exit={{ width: 0, opacity: 0 }}
            className="border-l border-[#222] bg-[#121212] flex flex-col h-full shrink-0">
            <div className="p-6 border-b border-[#222] flex justify-between items-center bg-[#0A0A0A]">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-[#1A1A1A] rounded-lg"><Network className="w-5 h-5 text-[#A78BFA]" /></div>
                <div><h2 className="font-bold text-white leading-tight">{selected.name}</h2>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${statusColor(selected.status).dot}`} />
                    <span className={`text-[10px] uppercase tracking-wider font-bold ${statusColor(selected.status).text}`}>{selected.status}</span>
                  </div>
                </div>
              </div>
              <button onClick={() => { setSelected(null); setChatMessages([]); }} className="p-2 text-gray-500 hover:text-white rounded-lg hover:bg-[#1A1A1A] transition-colors"><X className="w-5 h-5" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {selected.endpoint && (<div className="space-y-3"><h3 className="text-sm font-bold text-white">Endpoint</h3>
                <div className="bg-[#0A0A0A] border border-[#222] rounded-xl p-3 flex items-center justify-between">
                  <div><span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#8B5CF6]/20 text-[#A78BFA] mr-2">POST</span>
                  <span className="text-xs text-gray-300 font-mono">{API_BASE}{selected.endpoint}</span></div>
                  <button onClick={() => handleCopy(`${API_BASE}${selected.endpoint}`)} className="text-gray-500 hover:text-[#A78BFA] transition-colors p-1.5">
                    {copied ? <Copy className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>)}
              {selected.status === 'running' && (<div className="space-y-3 flex flex-col flex-1"><h3 className="text-sm font-bold text-white">Try it out</h3>
                <div className="bg-[#0A0A0A] border border-[#222] rounded-xl p-4 flex flex-col gap-3 min-h-[200px] max-h-[300px] overflow-y-auto">
                  {chatMessages.length === 0 && <div className="text-gray-600 text-xs text-center py-4">Send a message to test</div>}
                  {chatMessages.map((msg, i) => (<div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] text-sm px-3 py-2 rounded-2xl ${msg.role === 'user' ? 'bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 text-gray-200 rounded-tr-sm' : 'bg-[#1A1A1A] border border-[#222] text-gray-300 rounded-tl-sm'}`}>{msg.content}</div>
                  </div>))}
                  {chatLoading && <div className="flex justify-start"><div className="bg-[#1A1A1A] border border-[#222] text-gray-500 text-xs px-3 py-2 rounded-2xl flex items-center gap-2"><Loader2 className="w-3 h-3 animate-spin" /> Thinking...</div></div>}
                </div>
                <div className="relative">
                  <input type="text" placeholder="Enter a prompt..." value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleChatSend()}
                    className="w-full bg-[#0A0A0A] border border-[#222] rounded-xl pl-4 pr-12 py-3 text-sm text-white focus:outline-none focus:border-[#8B5CF6] transition-colors" />
                  <button onClick={handleChatSend} className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-[#8B5CF6] text-white rounded-lg hover:bg-[#7C3AED] transition-colors"><Send className="w-4 h-4" /></button>
                </div>
              </div>)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Deploy Modal */}
      <AnimatePresence>
        {showDeployModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="bg-[#121212] border border-[#222] rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden shadow-2xl">
              <div className="p-6 border-b border-[#222] flex justify-between items-center">
                <div><h2 className="text-lg font-bold text-white">Deploy Model</h2>
                <p className="text-xs text-gray-500 mt-1">Select a model from the registry to deploy via vLLM</p></div>
                <button onClick={() => setShowDeployModal(false)} className="p-2 text-gray-500 hover:text-white rounded-lg hover:bg-[#1A1A1A] transition-colors"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-6 overflow-y-auto max-h-[60vh] space-y-4">
                {!gpuEnabled && (
                  <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-4">
                    <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
                    <span className="text-sm text-red-300">GPU mode is disabled. Deployment will fail. Set <code className="bg-black/30 px-1.5 py-0.5 rounded text-xs">USE_GPU=true</code> in .env first.</span>
                  </div>
                )}
                {registry.map(model => (
                  <div key={model.id} className="bg-[#0A0A0A] border border-[#222] rounded-xl p-5 hover:border-[#8B5CF6]/30 transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-[#1A1A1A] rounded-lg">{typeIcon(model.type)}</div>
                        <div>
                          <h3 className="font-semibold text-white">{model.name}</h3>
                          <p className="text-xs text-gray-500 mt-0.5">{model.description}</p>
                          <div className="flex items-center gap-3 mt-2">
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#8B5CF6]/10 text-[#A78BFA] font-medium">{model.type}</span>
                            <span className="text-[10px] text-gray-600">{model.vram_required}</span>
                          </div>
                        </div>
                      </div>
                      <button onClick={() => handleDeploy(model)} disabled={deployingId === model.id || !gpuEnabled}
                        className="px-4 py-2 bg-gradient-to-r from-[#8B5CF6] to-[#6D28D9] text-white rounded-lg text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 shrink-0">
                        {deployingId === model.id ? <><Loader2 className="w-3 h-3 animate-spin" /> Deploying...</> : 'Deploy'}
                      </button>
                    </div>
                  </div>
                ))}
                {registry.length === 0 && <div className="text-center text-gray-500 text-sm py-8">No models in registry. Add models to data/model_registry.json.</div>}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
