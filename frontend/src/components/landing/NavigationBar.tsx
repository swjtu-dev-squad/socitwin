import { Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';

// Icon placeholder for removed lucide-react icon
const Github = BookOpen;

export default function NavigationBar() {
  return (
    <nav className="sticky top-0 z-50 h-16 glass-effect border-b border-border-default">
      <div className="w-full max-w-7xl mx-auto px-6 lg:px-12 xl:px-16 h-full flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center group">
          <img src="/logo-text.png" alt="Socitwin" className="h-10" />
        </Link>

        {/* Nav Links */}
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/your-org/socitwin"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg hover:bg-bg-tertiary transition-all duration-200 hover:scale-105"
            aria-label="访问 GitHub 仓库"
          >
            <Github className="w-5 h-5 text-text-secondary" />
          </a>
          <a
            href="https://docs.socitwin.com"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg hover:bg-bg-tertiary transition-all duration-200 hover:scale-105"
            aria-label="访问 Socitwin 文档"
          >
            <BookOpen className="w-5 h-5 text-text-secondary" />
          </a>
        </div>
      </div>
    </nav>
  );
}
