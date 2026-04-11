import { useState, useEffect } from 'react';
import { Archive, RefreshCw, Filter, ChevronRight, AlertCircle } from 'lucide-react';
import { listExperiments, type ExperimentListItem } from '../lib/experimentArchiveApi';

interface Props {
  onSelect: (id: string) => void;
  selectedId?: string;
}

export default function ExperimentArchiveTable({ onSelect, selectedId }: Props) {
  const [experiments, setExperiments] = useState<ExperimentListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filterDataset, setFilterDataset] = useState('');
  const [filterRec, setFilterRec] = useState('');

  const fetchList = async () => {
    setLoading(true);
    setError('');
    try {
      const list = await listExperiments();
      setExperiments(list);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchList(); }, []);

  const allDatasets = [...new Set(experiments.map(e => e.datasetId).filter(Boolean))];
  const allRecs = [...new Set(experiments.flatMap(e => e.recommenders))];

  const filtered = experiments.filter(e => {
    if (filterDataset && e.datasetId !== filterDataset) return false;
    if (filterRec && !e.recommenders.includes(filterRec)) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <Archive className="w-4 h-4 text-yellow-400" />
          历史实验 ({filtered.length})
        </h3>
        <button onClick={fetchList} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors">
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} /> 刷新
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <div className="flex items-center gap-1">
          <Filter className="w-3 h-3 text-gray-500" />
        </div>
        <select
          value={filterDataset}
          onChange={e => setFilterDataset(e.target.value)}
          className="bg-gray-700 text-white rounded px-2 py-1 text-xs border border-gray-600"
        >
          <option value="">全部数据集</option>
          {allDatasets.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <select
          value={filterRec}
          onChange={e => setFilterRec(e.target.value)}
          className="bg-gray-700 text-white rounded px-2 py-1 text-xs border border-gray-600"
        >
          <option value="">全部推荐器</option>
          {allRecs.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 rounded-lg p-2">
          <AlertCircle className="w-3 h-3 text-red-400" />
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {/* Table */}
      {filtered.length === 0 && !loading ? (
        <div className="flex flex-col items-center justify-center h-32 text-gray-500 bg-gray-700/30 rounded-xl">
          <Archive className="w-8 h-8 mb-2 opacity-30" />
          <p className="text-xs">暂无历史实验</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(exp => (
            <button
              key={exp.experimentId}
              onClick={() => onSelect(exp.experimentId)}
              className={`w-full text-left bg-gray-700/50 hover:bg-gray-700 rounded-xl p-3 transition-colors border ${
                selectedId === exp.experimentId ? 'border-blue-500' : 'border-transparent'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-medium truncate">{exp.name}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-400">{exp.datasetId}</span>
                    <span className="text-xs text-gray-500">·</span>
                    <span className="text-xs text-blue-300">{exp.recommenders.join(', ')}</span>
                    <span className="text-xs text-gray-500">·</span>
                    <span className="text-xs text-gray-400">{exp.steps} steps / seed {exp.seed}</span>
                  </div>
                  {exp.summary?.bestPolarization !== undefined && (
                    <div className="flex gap-3 mt-1">
                      <span className="text-xs text-gray-400">极化: <span className="text-white">{exp.summary.bestPolarization?.toFixed(4)}</span></span>
                      <span className="text-xs text-gray-400">速度: <span className="text-white">{exp.summary.bestVelocity?.toFixed(4)}</span></span>
                      <span className="text-xs text-gray-400">帖子: <span className="text-white">{exp.summary.totalPosts}</span></span>
                    </div>
                  )}
                </div>
                <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0 ml-2" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
