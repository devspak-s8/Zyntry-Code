import React from 'react';
import { motion } from 'motion/react';
import { TaskSession } from '../types';
import { StatusBadge } from './StatusBadge';
import { RivetLogo } from './RivetLogo';
import { 
  Plus, 
  SquareTerminal, 
  GitPullRequest, 
  ShieldCheck, 
  Scale,
  History,
  Sliders
} from 'lucide-react';

export type SidebarTab = 'chat' | 'changes' | 'verification' | 'constitution' | 'history' | 'settings';

interface SidebarProps {
  currentTab: SidebarTab;
  onSelectTab: (tab: SidebarTab) => void;
  sessions: TaskSession[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewTask: () => void;
  repoName?: string;
  branch?: string;
  activeFiles?: string[];
  runtime?: string;
  environment?: string;
  onCloseMobileDrawer?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewTask,
  onCloseMobileDrawer,
}) => {
  const navItems: { id: SidebarTab; label: string; icon: React.ReactNode; color: string }[] = [
    { 
      id: 'chat', 
      label: 'Chat', 
      icon: <SquareTerminal size={15} />, 
      color: 'text-[#93C5FD]' 
    },
    { 
      id: 'changes', 
      label: 'Changes', 
      icon: <GitPullRequest size={15} />, 
      color: 'text-[#82B9FF]' 
    },
    { 
      id: 'verification', 
      label: 'Verification', 
      icon: <ShieldCheck size={15} />, 
      color: 'text-[#55E6A5]' 
    },
    { 
      id: 'constitution', 
      label: 'Constitution', 
      icon: <Scale size={15} />, 
      color: 'text-[#93C5FD]' 
    },
    { 
      id: 'history', 
      label: 'History', 
      icon: <History size={15} />, 
      color: 'text-[#F4C76A]' 
    },
    { 
      id: 'settings', 
      label: 'Settings', 
      icon: <Sliders size={15} />, 
      color: 'text-[#93C5FD]' 
    },
  ];

  const handleSelectNav = (tab: SidebarTab) => {
    onSelectTab(tab);
    if (onCloseMobileDrawer) onCloseMobileDrawer();
  };

  const handleSelectSession = (id: string) => {
    onSelectSession(id);
    if (onCloseMobileDrawer) onCloseMobileDrawer();
  };

  return (
    <aside className="w-64 shrink-0 bg-[#0D1217]/95 border-r border-white/6 flex flex-col h-full text-xs select-none backdrop-blur-md">
      {/* 1. Header: Brand Logo & Workspace Title */}
      <div className="p-4 flex items-center justify-between border-b border-white/4">
        <div className="flex items-center gap-3">
          <RivetLogo size="md" />
          <div>
            <div className="font-semibold text-xs text-[#F3F4F6] tracking-tight flex items-center gap-1.5">
              <span>Zyntry Code</span>
            </div>
            <div className="text-[10px] text-[#9CA3AF] font-mono leading-none flex items-center gap-1 mt-0.5">
              <span>Engineering Agent</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. New Task Action Button */}
      <div className="px-3.5 pt-3.5 pb-2">
        <motion.button
          type="button"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onNewTask}
          className="w-full flex items-center justify-between py-2.5 px-3.5 bg-white/6 hover:bg-white/10 text-[#F3F4F6] border border-white/10 hover:border-white/20 rounded-2xl transition-all font-medium text-xs cursor-pointer shadow-sm group"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center text-white group-hover:scale-105 transition-transform">
              <Plus size={13} />
            </div>
            <span className="font-medium">New Task</span>
          </div>
          <span className="font-mono text-[10px] text-[#9CA3AF] bg-white/6 px-2 py-0.5 rounded-full border border-white/8">⌘N</span>
        </motion.button>
      </div>

      {/* 3. Primary Navigation Tabs */}
      <div className="px-3 py-2 space-y-1">
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleSelectNav(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-2xl transition-all text-xs font-medium cursor-pointer group ${
                isActive
                  ? 'bg-white/10 text-[#F3F4F6] border border-white/12 shadow-xs'
                  : 'text-[#9CA3AF] hover:text-[#F3F4F6] hover:bg-white/5 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`p-1.5 rounded-xl transition-transform group-hover:scale-110 ${
                    isActive
                      ? `${item.color} bg-white/10`
                      : 'text-[#6B7280] group-hover:text-[#F3F4F6]'
                  }`}
                >
                  {item.icon}
                </span>
                <span className={isActive ? 'font-semibold text-[#F3F4F6]' : ''}>{item.label}</span>
              </div>

              {isActive && (
                <div className="w-1.5 h-1.5 rounded-full bg-white shadow-xs" />
              )}
            </button>
          );
        })}
      </div>

      {/* Divider */}
      <div className="mx-4 my-1 border-t border-white/4" />

      {/* 4. Recent Tasks List */}
      <div className="flex-1 overflow-y-auto px-3.5 py-2.5 space-y-2.5">
        <div className="px-2 py-1 text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider">
          Recent Tasks
        </div>

        {sessions.map((sess) => {
          const isActive = sess.id === activeSessionId;
          return (
            <motion.button
              key={sess.id}
              type="button"
              whileHover={{ scale: 1.02, y: -1.5 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => handleSelectSession(sess.id)}
              className={`w-full text-left p-3.5 rounded-2xl transition-all text-xs cursor-pointer group border ${
                isActive
                  ? 'bg-white/[0.08] border-white/20 text-[#F3F4F6] shadow-md'
                  : 'bg-white/[0.025] hover:bg-white/[0.06] border-white/6 hover:border-white/12 text-[#9CA3AF] shadow-xs'
              }`}
            >
              <div className={`font-medium text-xs line-clamp-2 leading-relaxed ${isActive ? 'text-[#F2F6F4] font-semibold' : 'text-[#A3AEAA] group-hover:text-[#F2F6F4]'}`}>
                {sess.title}
              </div>

              <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-white/4 text-[10px]">
                <span className="font-mono text-[#6F7B77] group-hover:text-[#A3AEAA]">{sess.createdAt}</span>
                <StatusBadge state={sess.state} size="sm" />
              </div>
            </motion.button>
          );
        })}
      </div>
    </aside>
  );
};
