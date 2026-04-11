import type { Agent } from '@/lib/types';
import LandingForceGraph from './LandingForceGraph';

interface VisualColumnProps {
  className?: string;
  onNodeClick?: (agent: Agent) => void;
}

export default function VisualColumn({ className = '', onNodeClick }: VisualColumnProps) {
  const handleNodeClick = (agent: Agent) => {
    if (onNodeClick) {
      onNodeClick(agent);
    }
  };

  return (
    <div className={`relative w-full h-full flex items-center justify-center p-4 lg:p-6 ${className}`}>
      {/* 容器框 - 深灰色背景，点状网格，橙红色发光边框 */}
      <div
        className="relative w-full h-full rounded-2xl border-2 overflow-hidden animate-fade-in-scale"
        style={{
          borderColor: '#D72638',
          boxShadow: '0 0 20px rgba(215, 38, 56, 0.3), 0 0 40px rgba(215, 38, 56, 0.1), inset 0 0 20px rgba(215, 38, 56, 0.05)',
          background: '#1a1a1a',
          animationDelay: '0.5s',
        }}
      >
        {/* 点状网格背景 */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: 'radial-gradient(circle, #71717a 1px, transparent 1px)',
            backgroundSize: '20px 20px',
            opacity: 0.3,
          }}
        />

        {/* 人物肖像和气泡 */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative flex items-center gap-4 lg:gap-6">
            {/* 人物肖像 */}
            <div className="relative">
              <img
                src="/team-logo.png"
                alt="Team Member"
                className="w-32 h-32 lg:w-40 lg:h-40 object-cover rounded-2xl shadow-2xl"
              />
            </div>

            {/* 漫画风格气泡 */}
            <div className="relative">
              {/* 气泡主体 */}
              <div className="relative bg-white rounded-3xl px-5 py-3 shadow-xl">
                <div className="text-xl lg:text-2xl font-bold text-gray-800">
                  Coming Soon
                </div>
              </div>

              {/* 装饰性小圆点 */}
              <div className="absolute -top-2 -right-2 w-3 h-3 bg-accent rounded-full animate-bounce"></div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fade-in-scale {
          0% {
            opacity: 0;
            transform: scale(0.95);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }
        .animate-fade-in-scale {
          animation: fade-in-scale 0.8s ease-out forwards;
          opacity: 0;
        }
      `}</style>
    </div>
  );
}
