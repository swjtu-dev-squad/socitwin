import { Link } from 'react-router-dom';
import { Github, BookOpen } from 'lucide-react';
import { OasisIcon } from '@/components/OasisIcon';

export default function NavigationBar() {
  return (
    <nav className="sticky top-0 z-50 h-16 glass-effect border-b border-border-default">
      <div className="w-full max-w-7xl mx-auto px-6 lg:px-12 xl:px-16 h-full flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 group">
          <OasisIcon size={32} />
          <span className="text-lg font-bold gradient-text">OASIS DASHBOARD</span>
        </Link>

        {/* Nav Links */}
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/swjtu-dev-squad/oasis-dashboard"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg hover:bg-bg-tertiary transition-all duration-200 hover:scale-105"
            aria-label="访问 GitHub 仓库"
          >
            <Github className="w-5 h-5 text-text-secondary" />
          </a>
          <a
            href="https://docs.oasis.manus.computer"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg hover:bg-bg-tertiary transition-all duration-200 hover:scale-105"
            aria-label="访问 OASIS 文档"
          >
            <BookOpen className="w-5 h-5 text-text-secondary" />
          </a>
        </div>
      </div>
    </nav>
  );
}
