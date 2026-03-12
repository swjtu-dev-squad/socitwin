import { Link } from 'react-router-dom';
import { ArrowRight, Activity } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function Home() {
  const [scrollPosition, setScrollPosition] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setScrollPosition(prev => (prev + 0.5) % 100);
    }, 30);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Ambient background effects */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent/20 rounded-full blur-[128px] animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-light/10 rounded-full blur-[128px] animate-pulse" style={{ animationDelay: '1s' }}></div>
      </div>

      {/* Marquee - Ticker */}
      <div className="absolute top-0 left-0 right-0 h-12 border-b border-border-subtle overflow-hidden bg-bg-secondary/30 backdrop-blur-sm">
        <div className="absolute inset-0 flex items-center">
          <div
            className="flex whitespace-nowrap animate-marquee"
            style={{ transform: `translateX(-${scrollPosition}%)` }}
          >
            {[...Array(10)].map((_, i) => (
              <span key={i} className="inline-flex items-center gap-8 px-8 text-xs text-text-muted font-mono uppercase tracking-widest">
                <span className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse"></span>
                  Social Network Simulation
                </span>
                <span className="text-border-default">·</span>
                <span className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-accent-light rounded-full animate-pulse" style={{ animationDelay: '0.5s' }}></span>
                  Agent Behavior Analysis
                </span>
                <span className="text-border-default">·</span>
                <span className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse" style={{ animationDelay: '1s' }}></span>
                  Information Propagation
                </span>
                <span className="text-border-default">·</span>
                <span className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-accent-light rounded-full animate-pulse" style={{ animationDelay: '1.5s' }}></span>
                  Polarization Metrics
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="relative z-10 max-w-3xl mx-auto text-center space-y-16 mt-12">
        {/* Logo + Title */}
        <div className="flex items-center justify-center gap-8">
          {/* Logo */}
          <div className="relative group">
            {/* Outer glow */}
            <div className="absolute inset-0 rounded-2xl bg-accent/5 blur-3xl transition-opacity duration-700"></div>

            {/* Logo container */}
            <div className="relative w-24 h-24 flex items-center justify-center">
              <img
                src="/logo.png"
                alt="OASIS Logo"
                width={80}
                height={80}
                className="transform group-hover:scale-105 transition-transform duration-700 ease-out"
                style={{
                  borderRadius: '12px',
                  filter: 'brightness(0) invert(1)', // 白色
                }}
              />
            </div>
          </div>

          {/* Title */}
          <div className="text-left space-y-2">
            <h1 className="text-6xl font-black tracking-tight gradient-text animate-fade-in">
              OASIS
            </h1>

            <p className="text-sm text-accent font-mono uppercase tracking-[0.4em] opacity-80">
              Simulation OS
            </p>
          </div>
        </div>

        {/* Minimal descriptor */}
        <p className="text-base text-text-secondary max-w-md mx-auto leading-relaxed">
          社交网络模拟与行为分析
        </p>

        {/* Stats row */}
        <div className="flex items-center justify-center gap-12 text-text-muted">
          <div className="text-center space-y-1">
            <div className="text-2xl font-bold text-text-primary">AI Agents</div>
            <div className="text-[10px] uppercase tracking-wider">智能仿真</div>
          </div>
          <div className="w-px h-12 bg-border-default"></div>
          <div className="text-center space-y-1">
            <div className="text-2xl font-bold text-text-primary">Real-time</div>
            <div className="text-[10px] uppercase tracking-wider">实时监控</div>
          </div>
          <div className="w-px h-12 bg-border-default"></div>
          <div className="text-center space-y-1">
            <div className="text-2xl font-bold text-text-primary">Analysis</div>
            <div className="text-[10px] uppercase tracking-wider">深度分析</div>
          </div>
        </div>

        {/* CTA */}
        <div className="pt-8">
          <Link to="/overview">
            <button className="group relative inline-flex items-center gap-3 px-10 py-4 bg-gradient-to-r from-accent to-accent-light text-white rounded-xl font-semibold text-base transition-all hover:scale-105 hover:shadow-2xl hover:shadow-accent/25">
              <span>开始</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </Link>
        </div>

        {/* Footer */}
        <div className="pt-16 space-y-2">
          <p className="text-[10px] text-text-muted uppercase tracking-widest font-mono">
            v1.0.0 · Ready to Deploy
          </p>
        </div>
      </div>

      {/* Bottom ticker */}
      <div className="absolute bottom-0 left-0 right-0 h-12 border-t border-border-subtle overflow-hidden bg-bg-secondary/30 backdrop-blur-sm">
        <div className="absolute inset-0 flex items-center">
          <div
            className="flex whitespace-nowrap animate-marquee-reverse"
            style={{ transform: `translateX(${scrollPosition}%)` }}
          >
            {[...Array(8)].map((_, i) => (
              <span key={i} className="inline-flex items-center gap-12 px-8 text-xs text-text-muted font-mono">
                <span>System Online</span>
                <span className="w-1 h-1 bg-accent rounded-full"></span>
                <span>WebSocket Connected</span>
                <span className="w-1 h-1 bg-accent rounded-full"></span>
                <span>Engine Ready</span>
                <span className="w-1 h-1 bg-accent rounded-full"></span>
                <span>Agents Standing By</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @keyframes marquee-reverse {
          0% { transform: translateX(-50%); }
          100% { transform: translateX(0); }
        }
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-marquee {
          animation: marquee 30s linear infinite;
        }
        .animate-marquee-reverse {
          animation: marquee-reverse 25s linear infinite;
        }
        .animate-fade-in {
          animation: fade-in 1s ease-out forwards;
        }
      `}</style>
    </div>
  );
}
