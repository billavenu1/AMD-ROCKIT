import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Video, Image as ImageIcon, Send, Loader2,
  Play, Pause, Volume2, VolumeX, Maximize2,
  Search, Sparkles
} from 'lucide-react';

type VisionMode = 'Video Intelligence' | 'Image';

interface VideoMatch {
  id: number;
  video_name: string;
  start: string;
  end: string;
  start_seconds: number;
  end_seconds: number;
  score: number;
  frames: number;
}

interface ImageResult {
  id: number;
  file_name: string;
  file_size: string;
  resolution: string;
  score: number;
  url: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  matches?: VideoMatch[];
  images?: ImageResult[];
}

export const VisionView: React.FC = () => {
  const [mode, setMode] = useState<VisionMode>('Video Intelligence');
  const [prompt, setPrompt] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Video state
  const [videoMatches, setVideoMatches] = useState<VideoMatch[]>([]);
  const [activeVideoName, setActiveVideoName] = useState<string | null>(null);
  const [videoDuration, setVideoDuration] = useState(0);
  const [videoCurrentTime, setVideoCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Image state
  const [imageResults, setImageResults] = useState<ImageResult[]>([]);
  const [selectedImage, setSelectedImage] = useState<ImageResult | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Video time update
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onTime = () => setVideoCurrentTime(video.currentTime);
    const onDur  = () => setVideoDuration(video.duration);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    video.addEventListener('timeupdate', onTime);
    video.addEventListener('loadedmetadata', onDur);
    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);
    return () => {
      video.removeEventListener('timeupdate', onTime);
      video.removeEventListener('loadedmetadata', onDur);
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
    };
  }, [activeVideoName]);

  const handleAnalyze = useCallback(async () => {
    if (!prompt.trim() || isAnalyzing) return;
    const userPrompt = prompt;
    setPrompt('');
    setIsAnalyzing(true);

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userPrompt }]);

    try {
      const res = await fetch('/api/vision/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userPrompt, mode }),
      });

      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();

      if (mode === 'Video Intelligence') {
        const matches: VideoMatch[] = data.matches || [];
        setVideoMatches(matches);
        setImageResults([]);
        setSelectedImage(null);

        if (data.video_name) {
          setActiveVideoName(data.video_name);
        }

        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.reply || `Found ${matches.length} moments.`,
          matches,
        }]);

        // Auto-seek to first match
        if (matches.length > 0 && videoRef.current) {
          setSelectedMatchId(matches[0].id);
          setTimeout(() => {
            if (videoRef.current) {
              videoRef.current.currentTime = matches[0].start_seconds;
              videoRef.current.play().catch(() => {});
            }
          }, 500);
        }

      } else {
        const results: ImageResult[] = data.results || [];
        setImageResults(results);
        setVideoMatches([]);
        setActiveVideoName(null);

        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.reply || `Found ${results.length} images.`,
          images: results,
        }]);
      }

    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}. Make sure the backend is running.`,
      }]);
    } finally {
      setIsAnalyzing(false);
    }
  }, [prompt, mode, isAnalyzing]);

  const seekTo = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play().catch(() => {});
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) videoRef.current.play().catch(() => {});
    else videoRef.current.pause();
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setIsMuted(!isMuted);
  };

  const toggleFullscreen = () => {
    videoRef.current?.requestFullscreen?.();
  };

  const fmtTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const handleSeekBar = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !videoDuration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    videoRef.current.currentTime = pct * videoDuration;
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0A0A0A] overflow-hidden text-gray-300">
      {/* Header */}
      <div className="flex justify-between items-center px-8 py-5 border-b border-[#1A1A1A]">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-[#8B5CF6]" />
            Vision Intelligence
          </h1>
          <p className="text-gray-500 text-xs mt-1">Semantic search across videos and images using multimodal embeddings</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value as VisionMode);
                setVideoMatches([]);
                setImageResults([]);
                setSelectedImage(null);
              }}
              className="appearance-none pl-10 pr-8 py-2 bg-[#1A1A1A] border border-[#2A2A2A] rounded-lg text-sm text-white focus:outline-none focus:border-[#8B5CF6] transition-colors cursor-pointer"
            >
              <option value="Video Intelligence">Video Intelligence</option>
              <option value="Image">Image Search</option>
            </select>
            {mode === 'Video Intelligence' ? (
              <Video className="w-4 h-4 text-[#8B5CF6] absolute left-3 top-1/2 -translate-y-1/2" />
            ) : (
              <ImageIcon className="w-4 h-4 text-[#8B5CF6] absolute left-3 top-1/2 -translate-y-1/2" />
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">

        {/* Left: Chat Panel */}
        <div className="w-[420px] flex flex-col border-r border-[#1A1A1A]">
          <div className="flex-1 p-5 overflow-y-auto space-y-5">
            {/* Welcome */}
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center opacity-60">
                <Search className="w-10 h-10 text-[#8B5CF6] mb-4" />
                <p className="text-sm text-gray-400 max-w-[260px]">
                  {mode === 'Video Intelligence'
                    ? 'Ask a question about your video content and I\'ll find the exact moments.'
                    : 'Describe what you\'re looking for and I\'ll find matching images.'}
                </p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'items-start gap-3'}`}>
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] flex items-center justify-center shrink-0 mt-0.5">
                    <Sparkles className="w-3.5 h-3.5 text-white" />
                  </div>
                )}
                <div className={msg.role === 'user'
                  ? 'bg-[#8B5CF6]/15 border border-[#8B5CF6]/30 text-gray-100 text-sm px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-[85%]'
                  : 'max-w-[90%]'}>
                  {msg.role === 'user' ? (
                    <span>{msg.content}</span>
                  ) : (
                    <div>
                      <div className="bg-[#141414] border border-[#222] text-gray-200 text-sm px-4 py-3 rounded-2xl rounded-tl-sm leading-relaxed">
                        {msg.content}
                      </div>

                      {/* Video match cards */}
                      {msg.matches && msg.matches.length > 0 && (
                        <div className="mt-3 space-y-1.5">
                          {msg.matches.map((m) => (
                            <button
                              key={m.id}
                              onClick={() => {
                                setSelectedMatchId(m.id);
                                seekTo(m.start_seconds);
                              }}
                              className={`w-full bg-[#0E0E0E] border rounded-xl p-2.5 flex items-center gap-3 transition-all text-left
                                ${selectedMatchId === m.id
                                  ? 'border-[#8B5CF6] bg-[#8B5CF6]/5'
                                  : 'border-[#222] hover:border-[#8B5CF6]/40'
                                }`}
                            >
                              <div className={`p-1.5 rounded-lg ${selectedMatchId === m.id ? 'bg-[#8B5CF6]/20 text-[#A78BFA]' : 'bg-[#1A1A1A] text-gray-500'}`}>
                                <Play className="w-4 h-4" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-semibold text-white font-mono">{m.start} - {m.end}</div>
                                <div className="text-[10px] text-gray-500 mt-0.5">{m.frames} frame{m.frames > 1 ? 's' : ''} matched</div>
                              </div>
                              <div className="text-xs font-mono text-[#A78BFA] font-medium">{m.score.toFixed(2)}</div>
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Image result thumbnails in chat */}
                      {msg.images && msg.images.length > 0 && (
                        <div className="mt-3 grid grid-cols-3 gap-1.5">
                          {msg.images.slice(0, 6).map((img) => (
                            <button
                              key={img.id}
                              onClick={() => setSelectedImage(img)}
                              className={`aspect-square rounded-lg overflow-hidden border-2 transition-all
                                ${selectedImage?.id === img.id ? 'border-[#8B5CF6]' : 'border-transparent hover:border-[#8B5CF6]/40'}`}
                            >
                              <img src={img.url} alt={img.file_name} className="w-full h-full object-cover" />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isAnalyzing && (
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] flex items-center justify-center shrink-0">
                  <Sparkles className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="bg-[#141414] border border-[#222] text-gray-400 text-sm px-4 py-3 rounded-2xl rounded-tl-sm flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Analyzing with qwen3-vl-embedding-2b...
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-[#1A1A1A] bg-[#0A0A0A]">
            <div className="flex gap-2 mb-3 overflow-x-auto pb-1" style={{scrollbarWidth: 'none'}}>
              {(mode === 'Video Intelligence'
                ? ['Find animals', 'Action scenes', 'People talking', 'Landscape shots']
                : ['Red sports car', 'Nature scene', 'City skyline', 'Close-up shot']
              ).map((sug) => (
                <button
                  key={sug}
                  onClick={() => setPrompt(sug.toLowerCase())}
                  className="whitespace-nowrap px-3 py-1.5 rounded-lg bg-[#141414] border border-[#222] text-[11px] font-medium text-gray-400 hover:text-white hover:border-[#8B5CF6]/40 transition-colors"
                >
                  {sug}
                </button>
              ))}
            </div>
            <div className="relative">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                placeholder={mode === 'Video Intelligence' ? 'Describe what to find in the video...' : 'Describe the image you\'re looking for...'}
                disabled={isAnalyzing}
                className="w-full bg-[#141414] border border-[#222] rounded-xl pl-4 pr-12 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#8B5CF6] transition-colors disabled:opacity-50"
              />
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing || !prompt.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-[#8B5CF6] text-white rounded-lg hover:bg-[#7C3AED] transition-colors disabled:opacity-30"
              >
                {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>

        {/* Right: Results Panel */}
        <div className="flex-1 bg-[#0E0E0E] flex flex-col overflow-hidden">

          {/* ═══════════════ VIDEO MODE ═══════════════ */}
          {mode === 'Video Intelligence' && (
            <>
              {/* Video Player */}
              <div className="relative bg-black group">
                {activeVideoName ? (
                  <video
                    ref={videoRef}
                    src={`/api/vision/media/videos/${encodeURIComponent(activeVideoName)}`}
                    className="w-full max-h-[55vh] object-contain"
                    preload="metadata"
                  />
                ) : (
                  <div className="w-full aspect-video flex items-center justify-center">
                    <div className="text-center opacity-30">
                      <Video className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                      <p className="text-xs text-gray-600">Search to load video</p>
                    </div>
                  </div>
                )}

                {/* Controls overlay */}
                {activeVideoName && (
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent pt-10 pb-3 px-4 opacity-0 group-hover:opacity-100 transition-opacity">
                    {/* Seek bar with highlights */}
                    <div
                      className="w-full h-1.5 bg-white/15 rounded-full mb-3 cursor-pointer relative group/seek"
                      onClick={handleSeekBar}
                    >
                      {/* Match highlights */}
                      {videoMatches.map((m) => {
                        const left = videoDuration > 0 ? (m.start_seconds / videoDuration) * 100 : 0;
                        const width = videoDuration > 0 ? ((m.end_seconds - m.start_seconds + 5) / videoDuration) * 100 : 0;
                        return (
                          <div
                            key={m.id}
                            className={`absolute h-full rounded-full transition-colors ${
                              selectedMatchId === m.id ? 'bg-[#8B5CF6]' : 'bg-[#8B5CF6]/50'
                            }`}
                            style={{ left: `${left}%`, width: `${Math.max(width, 1)}%` }}
                            title={`${m.start} - ${m.end} (score: ${m.score})`}
                          />
                        );
                      })}
                      {/* Playhead */}
                      <div
                        className="absolute h-full bg-white rounded-full"
                        style={{ width: `${videoDuration > 0 ? (videoCurrentTime / videoDuration) * 100 : 0}%` }}
                      />
                      {/* Hover thumb */}
                      <div
                        className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-md opacity-0 group-hover/seek:opacity-100 transition-opacity"
                        style={{ left: `${videoDuration > 0 ? (videoCurrentTime / videoDuration) * 100 : 0}%`, transform: 'translate(-50%, -50%)' }}
                      />
                    </div>

                    {/* Bottom controls */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <button onClick={togglePlay} className="text-white hover:text-[#8B5CF6] transition-colors">
                          {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                        </button>
                        <button onClick={toggleMute} className="text-white/70 hover:text-white transition-colors">
                          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                        </button>
                        <span className="text-xs font-mono text-white/80">
                          {fmtTime(videoCurrentTime)} / {fmtTime(videoDuration)}
                        </span>
                      </div>
                      <button onClick={toggleFullscreen} className="text-white/70 hover:text-white transition-colors">
                        <Maximize2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Match cards below video */}
              {videoMatches.length > 0 && (
                <div className="flex-1 overflow-y-auto p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-xs font-semibold text-white uppercase tracking-wider">Matched Moments</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#8B5CF6]/15 text-[#A78BFA]">
                      {videoMatches.length}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
                    {videoMatches.map((m) => (
                      <button
                        key={m.id}
                        onClick={() => {
                          setSelectedMatchId(m.id);
                          seekTo(m.start_seconds);
                        }}
                        className={`rounded-xl border p-4 text-left transition-all group/card
                          ${selectedMatchId === m.id
                            ? 'border-[#8B5CF6] bg-[#8B5CF6]/8 shadow-lg shadow-[#8B5CF6]/10'
                            : 'border-[#1A1A1A] bg-[#121212] hover:border-[#8B5CF6]/40 hover:bg-[#141414]'
                          }`}
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <div className={`w-6 h-6 rounded-md flex items-center justify-center text-[10px] font-bold
                            ${selectedMatchId === m.id ? 'bg-[#8B5CF6] text-white' : 'bg-[#1A1A1A] text-gray-400'}`}>
                            {m.id}
                          </div>
                          <span className="text-sm font-semibold font-mono text-white">{m.start} - {m.end}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] text-gray-500">{m.frames} frame{m.frames > 1 ? 's' : ''}</span>
                          <span className="text-[11px] font-mono text-[#A78BFA] font-medium">score {m.score.toFixed(2)}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* ═══════════════ IMAGE MODE ═══════════════ */}
          {mode === 'Image' && (
            <div className="flex-1 overflow-y-auto p-5">
              {imageResults.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full opacity-30">
                  <ImageIcon className="w-12 h-12 text-gray-600 mb-3" />
                  <p className="text-xs text-gray-600">Search to find matching images</p>
                </div>
              )}

              {imageResults.length > 0 && (
                <>
                  {/* Selected image preview */}
                  {selectedImage && (
                    <div className="mb-5 rounded-xl overflow-hidden border border-[#222] bg-black">
                      <img
                        src={selectedImage.url}
                        alt={selectedImage.file_name}
                        className="w-full max-h-[50vh] object-contain"
                      />
                      <div className="px-4 py-3 bg-[#121212] flex items-center justify-between">
                        <div>
                          <span className="text-sm font-medium text-white">{selectedImage.file_name}</span>
                          <span className="text-xs text-gray-500 ml-3">{selectedImage.resolution}</span>
                          <span className="text-xs text-gray-500 ml-3">{selectedImage.file_size}</span>
                        </div>
                        <span className="text-xs font-mono text-[#A78BFA]">score {selectedImage.score.toFixed(4)}</span>
                      </div>
                    </div>
                  )}

                  {/* Image grid */}
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-xs font-semibold text-white uppercase tracking-wider">Results</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#8B5CF6]/15 text-[#A78BFA]">
                      {imageResults.length}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 xl:grid-cols-4 gap-3">
                    {imageResults.map((img) => (
                      <button
                        key={img.id}
                        onClick={() => setSelectedImage(img)}
                        className={`rounded-xl overflow-hidden border transition-all group/img
                          ${selectedImage?.id === img.id
                            ? 'border-[#8B5CF6] shadow-lg shadow-[#8B5CF6]/10 scale-[1.02]'
                            : 'border-[#1A1A1A] hover:border-[#8B5CF6]/40'
                          }`}
                      >
                        <div className="aspect-square bg-[#121212]">
                          <img
                            src={img.url}
                            alt={img.file_name}
                            className="w-full h-full object-cover group-hover/img:scale-105 transition-transform duration-300"
                          />
                        </div>
                        <div className="p-2 bg-[#121212]">
                          <div className="text-[10px] text-gray-400 truncate">{img.file_name}</div>
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-[10px] text-gray-600">{img.file_size}</span>
                            <span className="text-[10px] font-mono text-[#A78BFA]">{img.score.toFixed(2)}</span>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
