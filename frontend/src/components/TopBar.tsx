import React, { useState, useRef, useEffect } from 'react';
import { RoutingMode, RoutingInfo } from '../types';
import { 
  GitBranch, 
  FolderGit2, 
  Menu,
  ChevronDown,
  Check
} from 'lucide-react';

interface TopBarProps {
  repoName: string;
  branch: string;
  onBranchChange?: (branch: string) => void;
  runtime?: string;
  onRuntimeChange?: (runtime: string) => void;
  routingMode: RoutingMode;
  onRoutingModeChange: (rm: RoutingMode) => void;
  routingInfo: RoutingInfo;
  onToggleMobileSidebar: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  repoName,
  branch,
  routingMode,
  onRoutingModeChange,
  onToggleMobileSidebar,
}) => {
  const [showRoutingMenu, setShowRoutingMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const routingModes: RoutingMode[] = ['auto', 'fast', 'balanced', 'quality'];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowRoutingMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="h-13 sm:h-14 border-b border-white/6 bg-[#0D1217]/95 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between gap-3 shrink-0 select-none z-20">
      {/* Left: Mobile hamburger + Bubbly Repo & Branch Pill */}
      <div className="flex items-center gap-2.5 sm:gap-3 truncate">
        <button
          type="button"
          onClick={onToggleMobileSidebar}
          className="p-2 rounded-full text-[#A3AEAA] hover:text-[#F2F6F4] hover:bg-white/10 md:hidden cursor-pointer transition-colors shrink-0"
          title="Toggle workspace navigation"
        >
          <Menu size={16} />
        </button>

        {/* Bubbly Repository & Branch Pill */}
        <div className="flex items-center gap-2 px-3 sm:px-3.5 py-1.5 rounded-full bg-white/6 hover:bg-white/9 border border-white/10 text-xs font-mono text-[#F2F6F4] shadow-xs transition-colors">
          <FolderGit2 size={13} className="text-[#93C5FD] shrink-0" />
          <span className="font-semibold truncate">{repoName}</span>
          <span className="text-white/20">/</span>
          <div className="flex items-center gap-1.5 text-[#9CA3AF] truncate">
            <GitBranch size={11} className="text-[#93C5FD]/70 shrink-0" />
            <span className="truncate">{branch}</span>
          </div>
        </div>
      </div>

      {/* Right: Bubbly Model routing tier + context panel toggle */}
      <div className="flex items-center gap-2 sm:gap-2.5">
        {/* Model routing selector pill */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setShowRoutingMenu(!showRoutingMenu)}
            className="flex items-center gap-1.5 px-3 sm:px-3.5 py-1.5 rounded-full bg-white/6 hover:bg-white/10 border border-white/10 text-xs font-mono transition-all cursor-pointer shadow-xs"
            title="Configure routing policy"
          >
            <span className="text-[11px] text-[#9CA3AF] font-sans hidden sm:inline">Tier:</span>
            <span className="uppercase text-[#93C5FD] font-semibold tracking-wider">{routingMode}</span>
            <ChevronDown size={12} className={`text-[#9CA3AF] transition-transform ${showRoutingMenu ? 'rotate-180' : ''}`} />
          </button>

          {showRoutingMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-[#141A22] border border-white/12 rounded-2xl shadow-2xl p-1.5 z-50 backdrop-blur-xl space-y-1">
              <div className="px-2.5 py-1.5 text-[10px] uppercase font-mono text-[#9CA3AF] border-b border-white/6 pb-1.5 mb-1">
                Routing Tier
              </div>
              {routingModes.map((rm) => (
                <button
                  key={rm}
                  type="button"
                  onClick={() => {
                    onRoutingModeChange(rm);
                    setShowRoutingMenu(false);
                  }}
                  className={`w-full text-left px-2.5 py-1.5 text-xs font-mono uppercase rounded-xl flex items-center justify-between cursor-pointer transition-colors ${
                    routingMode === rm 
                      ? 'text-[#93C5FD] font-semibold bg-white/10' 
                      : 'text-[#9CA3AF] hover:text-[#F3F4F6] hover:bg-white/5'
                  }`}
                >
                  <span>{rm}</span>
                  {routingMode === rm && <Check size={12} className="text-[#93C5FD]" />}
                </button>
              ))}
            </div>
          )}
        </div>

        </div>
    </header>
  );
};
