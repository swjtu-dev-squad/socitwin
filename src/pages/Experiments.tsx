import React, { useState } from 'react';
import { FlaskConical, BarChart3, Archive } from 'lucide-react';
import ExperimentRunnerPanel from '../components/ExperimentRunnerPanel';
import ExperimentComparePanel from '../components/ExperimentComparePanel';
import ExperimentArchiveTable from '../components/ExperimentArchiveTable';
import ExperimentDetailDrawer from '../components/ExperimentDetailDrawer';

type Tab = 'runner' | 'compare' | 'archive';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'runner', label: '运行实验', icon: FlaskConical },
  { id: 'compare', label: '对比分析', icon: BarChart3 },
  { id: 'archive', label: '历史归档', icon: Archive },
];

export default function Experiments() {
  const [activeTab, setActiveTab] = useState<Tab>('runner');
  const [selectedExpId, setSelectedExpId] = useState<string | null>(null);

  return (
    <div className="p-6 space-y-6 relative">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <FlaskConical className="w-7 h-7 text-blue-400" />
          实验控制台
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          运行推荐策略对比实验、分析传播/极化/羊群差异、浏览历史实验记录
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-800 rounded-xl p-1 w-fit">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'runner' && <ExperimentRunnerPanel />}
        {activeTab === 'compare' && <ExperimentComparePanel />}
        {activeTab === 'archive' && (
          <div className="grid grid-cols-1 gap-6">
            <ExperimentArchiveTable
              onSelect={id => setSelectedExpId(id)}
              selectedId={selectedExpId || undefined}
            />
          </div>
        )}
      </div>

      {/* Detail Drawer (R6-03) */}
      {selectedExpId && activeTab === 'archive' && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setSelectedExpId(null)}
          />
          <ExperimentDetailDrawer
            experimentId={selectedExpId}
            onClose={() => setSelectedExpId(null)}
          />
        </>
      )}
    </div>
  );
}
