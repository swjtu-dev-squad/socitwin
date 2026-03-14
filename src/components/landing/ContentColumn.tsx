import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui';
import LoopingTypewriter from './LoopingTypewriter';

interface ContentColumnProps {
  className?: string;
}

export default function ContentColumn({ className = '' }: ContentColumnProps) {
  return (
    <div className={`flex flex-col justify-center space-y-6 lg:space-y-8 p-6 lg:p-8 ${className}`}>
      {/* Brand Section */}
      <div className="space-y-4 lg:space-y-6">
        <h1 className="text-4xl lg:text-5xl xl:text-6xl font-black gradient-text animate-fade-in leading-tight">
          OASIS DASHBOARD
        </h1>
      </div>

      {/* Bio */}
      <p className="text-base lg:text-lg text-text-secondary leading-relaxed max-w-lg animate-fade-in" style={{ animationDelay: '0.2s' }}>
        基于 <span className="text-accent">CAMEL-AI</span> 框架的可视化社会智能模拟平台
      </p>

      {/* 循环打字机效果 */}
      <div className="animate-fade-in" style={{ animationDelay: '0.3s' }}>
        <LoopingTypewriter
          texts={[
            '观测信息茧房',
            '分析舆论传播',
            '洞察群体极化',
          ]}
          speed={100}
          deleteSpeed={50}
          pauseDuration={2000}
        />
      </div>

      {/* CTA */}
      <div className="pt-2 lg:pt-4 animate-fade-in" style={{ animationDelay: '0.4s' }}>
        <Link to="/overview">
          <Button
            size="lg"
            variant="default"
            className="group gap-2 lg:gap-3 px-8 lg:px-10 py-3 lg:py-4 text-base lg:text-lg glow-effect hover:scale-105 transition-all duration-200"
          >
            开始
            <ArrowRight className="w-4 h-4 lg:w-5 lg:h-5 group-hover:translate-x-1 transition-transform" />
          </Button>
        </Link>
      </div>

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.8s ease-out forwards;
          opacity: 0;
        }
      `}</style>
    </div>
  );
}
