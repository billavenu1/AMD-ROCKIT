import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, SlidersHorizontal, Cpu, Eye, Database, X, Zap } from 'lucide-react';

interface DeployOption {
  label: string;
  value: string;
  vram_estimate: string;
}

interface Model {
  id: string;
  name: string;
  type: string;
  description: string;
  vram_required: string;
  icon: string;
  deploy_options: {
    quantization: DeployOption[];
    target_gpu: string[];
  };
}

export const ModelCatalogView: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);

  useEffect(() => {
    fetch('http://localhost:5055/api/catalog/models')
      .then(res => res.json())
      .then(data => setModels(data))
      .catch(err => console.error("Failed to fetch models:", err));
  }, []);

  const filteredModels = models.filter(m => m.name.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0A0A0A] overflow-hidden">
      {/* Header */}
      <div className="flex justify-between items-end p-8 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Model Catalog</h1>
          <p className="text-gray-400 text-sm">Browse and deploy models optimized for AMD GPUs.</p>
        </div>
        <div className="flex gap-4">
          <div className="relative">
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Search models..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-2 bg-[#1A1A1A] border border-[#2A2A2A] rounded-lg text-sm text-white focus:outline-none focus:border-[#8B5CF6] transition-colors w-64"
            />
          </div>
          <button className="p-2 bg-[#1A1A1A] border border-[#2A2A2A] rounded-lg text-gray-400 hover:text-white transition-colors">
            <SlidersHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-8 pt-4">
        <div className="grid grid-cols-2 gap-6">
          {filteredModels.map(model => (
            <ModelCard key={model.id} model={model} onDeploy={() => setSelectedModel(model)} />
          ))}
        </div>
      </div>

      <AnimatePresence>
        {selectedModel && (
          <DeployModal model={selectedModel} onClose={() => setSelectedModel(null)} />
        )}
      </AnimatePresence>
    </div>
  );
};

const ModelCard: React.FC<{ model: Model; onDeploy: () => void }> = ({ model, onDeploy }) => {
  const getIcon = () => {
    switch (model.icon) {
      case 'cpu': return <Cpu className="w-6 h-6 text-[#A78BFA]" />;
      case 'eye': return <Eye className="w-6 h-6 text-[#60A5FA]" />;
      case 'database': return <Database className="w-6 h-6 text-[#34D399]" />;
      default: return <Cpu className="w-6 h-6 text-[#A78BFA]" />;
    }
  };

  const getBadgeColor = () => {
    switch (model.type) {
      case 'LLM': return 'bg-[#8B5CF6]/20 text-[#A78BFA]';
      case 'Vision': return 'bg-[#3B82F6]/20 text-[#60A5FA]';
      case 'Embedding': return 'bg-[#10B981]/20 text-[#34D399]';
      default: return 'bg-gray-800 text-gray-300';
    }
  };

  return (
    <div className="bg-[#121212] border border-[#222] rounded-2xl p-6 flex flex-col justify-between group hover:border-[#8B5CF6]/50 transition-colors">
      <div>
        <div className="flex items-start gap-4 mb-4">
          <div className="p-3 bg-[#1A1A1A] rounded-xl group-hover:bg-[#8B5CF6]/10 transition-colors">
            {getIcon()}
          </div>
          <div>
            <h3 className="text-xl font-semibold text-white">{model.name}</h3>
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${getBadgeColor()} uppercase tracking-wider`}>
              {model.type}
            </span>
          </div>
        </div>
        <p className="text-gray-400 text-sm mb-8 leading-relaxed h-10 line-clamp-2">
          {model.description}
        </p>
      </div>

      <div>
        <div className="flex items-center gap-2 text-gray-500 text-xs uppercase tracking-wider font-semibold mb-2">
          <Cpu className="w-4 h-4" /> VRAM Required
        </div>
        <div className="text-lg font-medium text-white mb-6">{model.vram_required}</div>
        <button 
          onClick={onDeploy}
          className="w-full py-3 bg-[#8B5CF6]/10 hover:bg-[#8B5CF6] text-[#A78BFA] hover:text-white rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2 group-hover:shadow-[0_0_20px_rgba(139,92,246,0.3)]"
        >
          Deploy <Zap className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

const DeployModal: React.FC<{ model: Model; onClose: () => void }> = ({ model, onClose }) => {
  const [quantization, setQuantization] = useState(model.deploy_options.quantization[0]?.value || '');
  const [targetGpu, setTargetGpu] = useState(model.deploy_options.target_gpu[0] || '');
  const [isDeploying, setIsDeploying] = useState(false);

  const selectedQuant = model.deploy_options.quantization.find(q => q.value === quantization);

  const handleDeploy = async () => {
    setIsDeploying(true);
    try {
      await fetch('http://localhost:5055/api/catalog/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: model.id,
          quantization,
          target_gpu: targetGpu
        })
      });
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setIsDeploying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="bg-[#121212] border border-[#2A2A2A] rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden"
      >
        <div className="p-6 border-b border-[#2A2A2A] flex justify-between items-start">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">Deploy {model.name}</h2>
            <p className="text-sm text-gray-400">Configure your deployment settings. You can modify these later.</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Quantization */}
          <div>
            <label className="block text-sm font-medium text-white mb-1">Quantization</label>
            <p className="text-xs text-gray-400 mb-3">Select the quantization level for optimal performance.</p>
            <div className="flex bg-[#0A0A0A] p-1 rounded-xl border border-[#2A2A2A]">
              {model.deploy_options.quantization.map(q => (
                <button
                  key={q.value}
                  onClick={() => setQuantization(q.value)}
                  className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
                    quantization === q.value 
                    ? 'bg-[#1A1A1A] text-white shadow-sm border border-[#333]' 
                    : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>

          {/* Target GPU */}
          <div>
            <label className="block text-sm font-medium text-white mb-1">Target GPU</label>
            <p className="text-xs text-gray-400 mb-3">Select the GPU to run this model on.</p>
            <select 
              value={targetGpu}
              onChange={(e) => setTargetGpu(e.target.value)}
              className="w-full bg-[#0A0A0A] border border-[#2A2A2A] rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#8B5CF6] transition-colors appearance-none"
            >
              {model.deploy_options.target_gpu.map(gpu => (
                <option key={gpu} value={gpu}>{gpu}</option>
              ))}
            </select>
          </div>

          {/* Memory Estimate */}
          <div>
            <label className="block text-sm font-medium text-white mb-1">Memory Estimate</label>
            <p className="text-xs text-gray-400 mb-3">Estimated VRAM requirement for this configuration.</p>
            <div className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-xl px-4 py-3 flex items-center gap-3">
              <Cpu className="w-5 h-5 text-[#8B5CF6]" />
              <span className="text-sm font-medium text-white">{selectedQuant?.vram_estimate || model.vram_required}</span>
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-[#2A2A2A] flex justify-between gap-4 bg-[#0A0A0A]">
          <button 
            onClick={onClose}
            className="px-6 py-2.5 rounded-xl text-sm font-medium text-white hover:bg-[#1A1A1A] border border-[#2A2A2A] transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleDeploy}
            disabled={isDeploying}
            className="flex-1 px-6 py-2.5 bg-[#8B5CF6] hover:bg-[#7C3AED] text-white rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(139,92,246,0.3)] disabled:opacity-50"
          >
            {isDeploying ? 'Deploying...' : 'Deploy'} <Zap className="w-4 h-4" />
          </button>
        </div>
      </motion.div>
    </div>
  );
};
