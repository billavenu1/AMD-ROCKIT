import React, { useState, useEffect } from 'react';
import { 
  ChevronDown, 
  X,
  Loader2,
  Check
} from 'lucide-react';

const API_BASE = 'http://localhost:5055';

export const DeployAgentsView: React.FC = () => {
  const [model, setModel] = useState('');
  const [availableModels, setAvailableModels] = useState<{id: string, name: string}[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/catalog/available-models`)
      .then(res => res.json())
      .then(data => {
        setAvailableModels(data);
        if (data && data.length > 0) {
          setModel(data[0].id);
        }
      })
      .catch(err => console.error("Failed to fetch available models:", err));
  }, []);
  const [instructions, setInstructions] = useState('');
  const [knowledgeType, setKnowledgeType] = useState('Vision');
  const [knowledgeSource, setKnowledgeSource] = useState('Image');
  const [toolsActive, setToolsActive] = useState(['Code Execution', 'Database']);
  const [workflowName, setWorkflowName] = useState('');
  
  const [activeTab, setActiveTab] = useState('Chat');
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [publishedEndpoint, setPublishedEndpoint] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // Chat preview state
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<{role: string; content: string}[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  const removeTool = (tool: string) => {
    setToolsActive(toolsActive.filter(t => t !== tool));
  };

  const buildPayload = () => ({
    name: workflowName || `${model} Workflow`,
    model,
    instructions,
    knowledge: { type: knowledgeType, source: knowledgeSource },
    tools: toolsActive,
  });

  const handleSave = async () => {
    setSaving(true);
    setStatusMsg(null);
    try {
      if (savedId) {
        // Update existing
        await fetch(`${API_BASE}/api/workflows/${savedId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        });
        setStatusMsg('Workflow updated');
      } else {
        // Create new
        const res = await fetch(`${API_BASE}/api/workflows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        });
        const data = await res.json();
        setSavedId(data.workflow_id);
        setStatusMsg(`Saved as ${data.workflow_id}`);
      }
    } catch (e: any) {
      setStatusMsg(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMsg(null), 3000);
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    setStatusMsg(null);
    try {
      // Save first if not saved yet
      let wfId = savedId;
      if (!wfId) {
        const res = await fetch(`${API_BASE}/api/workflows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        });
        const data = await res.json();
        wfId = data.workflow_id;
        setSavedId(wfId);
      }

      // Publish
      const pubRes = await fetch(`${API_BASE}/api/workflows/${wfId}/publish`, {
        method: 'POST',
      });
      const pubData = await pubRes.json();
      setPublishedEndpoint(pubData.endpoint);
      setStatusMsg(`Published! Endpoint: ${pubData.endpoint}`);
    } catch (e: any) {
      setStatusMsg(`Publish failed: ${e.message}`);
    } finally {
      setPublishing(false);
    }
  };

  const handleChatSend = async () => {
    if (!chatInput.trim() || !savedId || !publishedEndpoint) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/workflows/${savedId}/invoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg }),
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (e: any) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex h-full w-full bg-black overflow-hidden text-white font-sans">
      {/* Left Panel - Workflow Builder */}
      <div className="w-[40%] min-w-[350px] max-w-[450px] flex flex-col border-r border-[#1F1F1F]">
        {/* Top Bar */}
        <div className="h-20 px-6 flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">Create Workflow</h1>
          <div className="flex items-center gap-3">
            <button 
              onClick={handleSave} 
              disabled={saving}
              className="px-4 py-1.5 rounded-lg border border-gray-700 text-sm font-medium hover:bg-gray-900 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : savedId ? <Check className="w-3 h-3 text-emerald-400" /> : null}
              Save
            </button>
            <button 
              onClick={handlePublish}
              disabled={publishing}
              className="px-4 py-1.5 rounded-lg bg-[#a855f7] hover:bg-[#9333ea] text-white text-sm font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {publishing ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
              Publish
            </button>
          </div>
        </div>

        {/* Status Message */}
        {statusMsg && (
          <div className="mx-6 mb-2 px-3 py-2 rounded-lg bg-[#1A1A2E] border border-[#8B5CF6]/30 text-xs text-[#A78BFA] font-mono">
            {statusMsg}
          </div>
        )}

        {/* Scrollable Config Sections */}
        <div className="flex-1 overflow-y-auto px-6 pb-8 space-y-6 custom-scrollbar">
          
          {/* Workflow Name */}
          <div className="space-y-2">
            <div className="text-xs text-gray-400">Workflow Name</div>
            <input 
              type="text"
              className="w-full bg-[#0f1117] border border-transparent rounded-xl px-4 py-3 text-sm text-gray-200 focus:outline-none focus:border-gray-600"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              placeholder="e.g. HR Q&A Agent"
            />
          </div>

          {/* Model Section */}
          <div className="space-y-2">
            <div className="text-xs text-gray-400">Model</div>
            <div className="relative">
              <select 
                className="w-full appearance-none bg-[#0a0a0c] border border-gray-300 rounded-xl px-4 py-3 text-sm text-gray-200 focus:outline-none focus:border-white transition-colors"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {availableModels.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
                {availableModels.length === 0 && <option value="">Loading...</option>}
              </select>
              <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            </div>
          </div>

          {/* Instructions Section */}
          <div className="space-y-2">
            <div className="text-xs text-gray-400">Instructions</div>
            <div className="relative">
              <textarea 
                className="w-full h-32 bg-[#0f1117] border border-transparent rounded-xl px-4 py-3 text-sm text-gray-200 focus:outline-none focus:border-gray-600 resize-none"
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder="You are a helpful assistant..."
              />
              <div className="absolute bottom-2 right-3 text-[10px] text-gray-500">
                {instructions.length} chars
              </div>
            </div>
          </div>

          {/* Knowledge Section */}
          <div className="space-y-2">
            <div className="text-xs text-gray-400">Knowledge</div>
            <div className="flex gap-3">
              <div className="relative flex-1">
                <select 
                  className="w-full appearance-none bg-[#0f1117] border border-transparent rounded-xl px-4 py-3 text-sm text-gray-200 focus:outline-none focus:border-gray-600"
                  value={knowledgeType}
                  onChange={(e) => {
                    setKnowledgeType(e.target.value);
                    if (e.target.value === 'Grounded Project') {
                      setKnowledgeSource('HR Index');
                    } else {
                      setKnowledgeSource('Image');
                    }
                  }}
                >
                  <option value="Grounded Project">Grounded Project</option>
                  <option value="Vision">Vision</option>
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              </div>
              <div className="relative flex-1">
                <select 
                  className="w-full appearance-none bg-[#0f1117] border border-transparent rounded-xl px-4 py-3 text-sm text-gray-200 focus:outline-none focus:border-gray-600"
                  value={knowledgeSource}
                  onChange={(e) => setKnowledgeSource(e.target.value)}
                >
                  {knowledgeType === 'Grounded Project' ? (
                    <>
                      <option value="HR Index">HR Index</option>
                      <option value="Sales">Sales</option>
                      <option value="Finance">Finance</option>
                    </>
                  ) : (
                    <>
                      <option value="Image">Image</option>
                      <option value="Video Intelligence">Video Intelligence</option>
                    </>
                  )}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              </div>
            </div>
          </div>

          {/* Tools Section */}
          <div className="space-y-3">
            <div className="text-xs text-gray-400">Tools</div>
            <div className="flex flex-wrap gap-2">
              {toolsActive.map(tool => (
                <div key={tool} className="flex items-center gap-1.5 px-3 py-1 bg-[#a855f7] rounded-full text-xs font-medium text-white">
                  <span>{tool}</span>
                  <X 
                    className="w-3 h-3 cursor-pointer hover:text-gray-200" 
                    onClick={() => removeTool(tool)}
                  />
                </div>
              ))}
            </div>
            <button className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-gray-600 text-sm font-medium hover:bg-[#111115] transition-colors mt-2">
              + Explore Tools
            </button>
          </div>

          {/* Published Endpoint Info */}
          {publishedEndpoint && (
            <div className="p-4 bg-[#0B1D0B] border border-emerald-500/30 rounded-xl space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]" />
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Published</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#8B5CF6]/20 text-[#A78BFA]">POST</span>
                <code className="text-xs text-gray-300 font-mono">{API_BASE}{publishedEndpoint}</code>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Right Panel - Chat Preview */}
      <div className="flex-1 flex flex-col bg-black">
        {/* Top Bar */}
        <div className="h-20 px-8 flex items-center justify-between border-b border-[#1F1F1F]">
          <div className="flex items-center gap-6">
            <span className="text-sm font-medium text-gray-500">Preview</span>
            <div className="flex items-center gap-5">
              {['Chat', 'YAML', 'Code'].map(tab => (
                <button 
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`text-sm font-medium transition-colors ${activeTab === tab ? 'text-white' : 'text-gray-400 hover:text-gray-200'}`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
          <button className="px-4 py-1.5 rounded-lg border border-gray-700 text-sm font-medium text-white hover:bg-[#1A1A1A] transition-colors">
            Metrics
          </button>
        </div>

        {/* Chat Area */}
        {activeTab === 'Chat' && (
          <div className="flex-1 flex flex-col">
            {/* Messages or Empty State */}
            <div className="flex-1 overflow-y-auto p-8">
              {chatMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center">
                  <h2 className="text-2xl font-semibold mb-3">{model}</h2>
                  <p className="text-gray-500 text-sm mb-1">
                    Use agent configuration to update the description and starter prompts
                  </p>
                  {!publishedEndpoint && (
                    <p className="text-gray-600 text-xs mt-4">
                      Publish the workflow to start chatting
                    </p>
                  )}
                </div>
              ) : (
                <div className="max-w-3xl mx-auto space-y-6">
                  {chatMessages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                        msg.role === 'user' 
                          ? 'bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 text-gray-200 rounded-tr-sm'
                          : 'bg-[#1A1A1A] border border-[#222] text-gray-300 rounded-tl-sm'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <div className="bg-[#1A1A1A] border border-[#222] text-gray-500 text-sm px-4 py-3 rounded-2xl rounded-tl-sm flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Thinking...
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Bottom Chat Input */}
            <div className="p-6 flex flex-col items-center">
              <div className="w-full max-w-3xl relative">
                <input 
                  type="text" 
                  placeholder={publishedEndpoint ? "Message the agent..." : "Publish workflow to chat..."}
                  disabled={!publishedEndpoint}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleChatSend()}
                  className="w-full bg-[#0f1117] border border-transparent rounded-xl px-4 py-3.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-600 disabled:opacity-50"
                />
              </div>
              <div className="mt-3 text-xs text-gray-600">
                AI-generated content may be incorrect
              </div>
            </div>
          </div>
        )}

        {/* YAML Tab */}
        {activeTab === 'YAML' && (
          <div className="flex-1 overflow-y-auto p-8">
            <pre className="bg-[#0f1117] border border-[#222] rounded-xl p-6 text-sm text-gray-300 font-mono whitespace-pre-wrap">
{`# Workflow Configuration
name: "${workflowName || `${model} Workflow`}"
model: "${model}"
instructions: |
  ${instructions || '(none)'}
knowledge:
  type: "${knowledgeType}"
  source: "${knowledgeSource}"
tools:
${toolsActive.map(t => `  - "${t}"`).join('\n')}
${publishedEndpoint ? `\n# Published Endpoint\nendpoint: "${API_BASE}${publishedEndpoint}"` : '# Status: Draft (not published yet)'}
`}
            </pre>
          </div>
        )}

        {/* Code Tab */}
        {activeTab === 'Code' && (
          <div className="flex-1 overflow-y-auto p-8">
            <pre className="bg-[#0f1117] border border-[#222] rounded-xl p-6 text-sm text-gray-300 font-mono whitespace-pre-wrap">
{`import requests

# Invoke the workflow
response = requests.post(
    "${API_BASE}${publishedEndpoint || `/api/workflows/<workflow_id>/invoke`}",
    json={"message": "Your question here"},
    headers={"Content-Type": "application/json"}
)

print(response.json()["response"])
`}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
