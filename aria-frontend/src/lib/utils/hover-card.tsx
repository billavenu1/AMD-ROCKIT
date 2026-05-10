import React, { useState, useEffect, useRef } from 'react';

interface ChunkData {
  text_content: string;
  image_paths: string[];
  source_title?: string;
}

export function ChunkHoverCard({ chunkId, type = 'chunk', children }: { chunkId: string, type?: string, children: React.ReactNode }) {
  const [isHovered, setIsHovered] = useState(false);
  const [chunkData, setChunkData] = useState<ChunkData | null>(null);
  const [isTop, setIsTop] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setIsHovered(false);
    }, 200); // 200ms delay to allow moving mouse to the tooltip
  };

  useEffect(() => {
    if (isHovered && !chunkData) {
      // Helper to map a source API response into ChunkData shape
      const mapSourceToChunk = (data: any): ChunkData => {
        const fullText = data.full_text || '';
        const previewText = fullText
          ? fullText.substring(0, 500) + (fullText.length > 500 ? '…' : '')
          : 'Source is still processing or has no extractable text.';
        return {
          text_content: previewText,
          image_paths: [],
          source_title: data.title || 'Document'
        };
      };

      // Helper to map a chunk API response into ChunkData shape
      const mapChunkToChunk = (data: any): ChunkData => ({
        text_content: data.text_content || '',
        image_paths: data.image_paths || [],
        source_title: data.source_title
      });

      // Always try chunk endpoint first (IDs are most often chunk IDs with
      // the source_chunk: prefix stripped by the chat graph). Fall back to
      // the source endpoint if that 404s.
      fetch(`/api/sources/chunks/${chunkId}`)
        .then(res => {
          if (res.ok) return res.json().then(data => {
            console.log(`[Hover] Fetched chunk:`, data);
            setChunkData(mapChunkToChunk(data));
          });
          // Chunk not found — try as a source
          return fetch(`/api/sources/${chunkId}`)
            .then(res2 => {
              if (!res2.ok) throw new Error(`HTTP ${res2.status}`);
              return res2.json();
            })
            .then(data => {
              console.log(`[Hover] Fetched source:`, data);
              setChunkData(mapSourceToChunk(data));
            });
        })
        .catch(err => {
          console.warn(`[Hover] Could not fetch content for ${type}:${chunkId}`, err);
          setChunkData({
            text_content: 'Content no longer available.',
            image_paths: [],
            source_title: 'Unavailable'
          });
        });
    }
  }, [isHovered, chunkId, chunkData, type]);

  // Handle positioning
  useEffect(() => {
    if (isHovered && cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      const windowHeight = window.innerHeight;
      // If the tooltip goes below the window, show it above the text instead
      if (rect.bottom > windowHeight - 20) {
        setIsTop(true);
      } else {
        setIsTop(false);
      }
    }
  }, [isHovered, chunkData]);

  return (
    <div
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {isHovered && chunkData && (
        <div 
          ref={cardRef}
          className={`absolute z-50 w-[350px] bg-[#222] text-white rounded-xl shadow-2xl border border-[#444] transform -translate-x-1/2 left-1/2 ${
            isTop ? 'bottom-full mb-2' : 'top-full mt-2'
          } animate-in fade-in zoom-in duration-200 overflow-hidden`}
        >
          {/* Header */}
          <div className="px-4 pt-4 pb-2">
            <h4 className="font-bold text-sm text-gray-100 truncate flex items-center gap-2">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
              {chunkData.source_title || 'Document'}
            </h4>
          </div>

          {/* Content */}
          <div className="px-4 pb-3">
            <p className="text-[13px] text-gray-300 leading-relaxed max-h-[200px] overflow-y-auto custom-scrollbar pr-2">
              {chunkData.text_content}
            </p>
          </div>

          {/* Images */}
          {chunkData.image_paths && chunkData.image_paths.length > 0 && (
            <div className="px-4 pb-3">
              <div className="flex gap-2 overflow-x-auto custom-scrollbar snap-x pb-2">
                {chunkData.image_paths.map((img, i) => (
                  <img
                    key={i}
                    src={`http://localhost:5055${img}`}
                    alt="Extracted"
                    className="h-28 w-auto max-w-[250px] object-contain rounded-md bg-[#111] border border-[#333] snap-start shrink-0"
                  />
                ))}
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="px-4 py-3 bg-[#1e1e1e] border-t border-[#333] flex justify-between items-center text-[12px] font-medium text-gray-400">
            <span className="hover:text-white cursor-pointer transition-colors">View source</span>
            <span className="flex items-center gap-1 hover:text-white cursor-pointer transition-colors">
              1 source
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
