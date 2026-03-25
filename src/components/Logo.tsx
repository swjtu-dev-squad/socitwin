import React from 'react';

export const Logo = ({ className }: { className?: string }) => {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Graphic */}
      <div className="relative w-10 h-10 flex items-center justify-center shrink-0">
        {/* Left Circle - Solid (Real Baseline) - Silver White */}
        <div className="absolute left-0.5 w-6 h-6 rounded-full border-[2px] border-[#E2E8F0]" />
        
        {/* Right Circle - Dashed (Simulation) - Cobalt Blue */}
        <div className="absolute right-0.5 w-6 h-6 rounded-full border-[2px] border-[#0047AB] border-dashed animate-[spin_15s_linear_infinite]" />
        
        {/* Core Dot - Intersection - Bright White */}
        <div className="absolute w-2 h-2 bg-white rounded-full shadow-[0_0_10px_2px_rgba(255,255,255,0.9)] z-10" />
      </div>

      {/* Text */}
      <div className="flex flex-col justify-center">
        <div className="font-sans font-black text-xl tracking-[0.1em] flex items-center text-[#E2E8F0] leading-none">
          <span>SOC</span>
          <div className="relative flex flex-col items-center justify-end h-5 mx-[2px]">
            <div className="w-1.5 h-1.5 bg-[#0047AB] rounded-full animate-pulse absolute top-0 shadow-[0_0_8px_rgba(0,71,171,0.8)]" />
            <div className="w-1.5 h-3 bg-[#E2E8F0] absolute bottom-0" />
          </div>
          <span>TWIN</span>
        </div>
        <p className="text-[8px] text-[#E2E8F0]/60 font-bold uppercase tracking-widest mt-1">
          STW System
        </p>
      </div>
    </div>
  );
};
