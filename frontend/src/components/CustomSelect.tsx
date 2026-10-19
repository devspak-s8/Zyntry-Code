import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronDown, Check } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
  desc?: string;
  badge?: string;
  icon?: React.ReactNode;
}

interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  align?: 'left' | 'right';
}

export const CustomSelect: React.FC<CustomSelectProps> = ({
  value,
  onChange,
  options,
  placeholder = 'Select an option...',
  disabled = false,
  className = '',
  align = 'left',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  return (
    <div className={`relative w-full ${className}`} ref={containerRef}>
      {/* Trigger Button - Bubbly pill styling */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`w-full h-11 px-4 rounded-full flex items-center justify-between text-xs transition-all cursor-pointer ${
          disabled
            ? 'bg-white/4 border border-white/8 text-[#6B7280] cursor-not-allowed opacity-60'
            : isOpen
            ? 'bg-[#151E29] border border-white/30 text-white shadow-lg shadow-black/40 ring-2 ring-white/10'
            : 'bg-[#0F141A] hover:bg-[#141C25] border border-white/12 hover:border-white/20 text-[#F3F4F6] shadow-sm'
        }`}
      >
        <div className="flex items-center gap-2.5 truncate mr-2">
          {selectedOption?.icon && (
            <span className="text-[#93C5FD] shrink-0">{selectedOption.icon}</span>
          )}
          <span className="truncate font-medium">
            {selectedOption ? selectedOption.label : placeholder}
          </span>
          {selectedOption?.badge && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 border border-white/10 text-[#93C5FD] shrink-0">
              {selectedOption.badge}
            </span>
          )}
        </div>
        <ChevronDown
          size={14}
          className={`shrink-0 text-[#9CA3AF] transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-[#93C5FD]' : ''
          }`}
        />
      </button>

      {/* Dropdown Menu Popover */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.97 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className={`absolute z-50 mt-1.5 w-full min-w-[240px] max-h-72 overflow-y-auto rounded-[22px] bg-[#141C25]/98 border border-white/16 shadow-2xl p-2 backdrop-blur-2xl ${
              align === 'right' ? 'right-0' : 'left-0'
            }`}
          >
            <div className="space-y-1">
              {options.map((option) => {
                const isSelected = option.value === value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      onChange(option.value);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left px-3.5 py-2.5 rounded-xl flex items-start justify-between gap-3 text-xs transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-white/12 text-white font-medium shadow-xs'
                        : 'text-[#9CA3AF] hover:text-[#F3F4F6] hover:bg-white/6'
                    }`}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      {option.icon && (
                        <span className={`mt-0.5 shrink-0 ${isSelected ? 'text-[#93C5FD]' : 'text-[#6B7280]'}`}>
                          {option.icon}
                        </span>
                      )}
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`truncate ${isSelected ? 'text-white font-semibold' : 'text-[#D1D5DB]'}`}>
                            {option.label}
                          </span>
                          {option.badge && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/8 text-[#93C5FD]">
                              {option.badge}
                            </span>
                          )}
                        </div>
                        {option.desc && (
                          <div className="text-[11px] text-[#6B7280] mt-0.5 leading-relaxed font-normal">
                            {option.desc}
                          </div>
                        )}
                      </div>
                    </div>
                    {isSelected && (
                      <Check size={14} className="text-[#93C5FD] shrink-0 mt-0.5" />
                    )}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
