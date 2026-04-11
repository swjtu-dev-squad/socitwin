import { useState } from 'react';
import { Play, Loader2, AlertCircle, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import { runExperiment, type ExperimentFormState, type ExperimentRunResult } from '../lib/experimentApi';

const RECOMMENDERS = [
  { id: 'tiktok', label: 'TikTok', desc: '短期兴趣 + 完播率' },
  { id: 'xiaohongshu', label: '小红书', desc: '内容质量 + 社交亲密度' },
  { id: 'pinterest', label: 'Pinterest', desc: '长期兴趣 + 画板相似度' },
];

const PLATFORMS = ['REDDIT', 'X', 'FACEBOOK', 'TIKTOK', 'INSTAGRAM'] as const;
const DATASETS = [
  { id: 'demo', label: 'Demo Reddit 数据集' },
  { id: 'dataset_demo_reddit', label: 'Reddit 演示数据集' },
  { id: 'dataset_demo_csv', label: 'CSV 演示数据集' },
];

const DEFAULT_FORM: ExperimentFormState = {
  name: '',
  datasetId: 'demo',
  recommenders: ['tiktok', 'xiaohongshu'],
  platform: 'REDDIT',
  steps: 15,
  seed: 42,
  agentCount: 10,
};

type RunStatus = 'idle' | 'running' | 'success' | 'error';

export default function ExperimentRunnerPanel() {
  const [form, setForm] = useState<ExperimentFormState>(DEFAULT_FORM);
  const [status, setStatus] = useState<RunStatus>('idle');
  const [result, setResult] = useState<ExperimentRunResult | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [showDetails, setShowDetails] = useState(false);

  const toggleRecommender = (id: string) => {
    setForm(prev => ({
      ...prev,
      recommenders: prev.recommenders.includes(id)
        ? prev.recommenders.filter(r => r !== id)
        : [...prev.recommenders, id],
    }));
  };

  const handleRun = async () => {
    if (form.recommenders.length < 1) {
      setErrorMsg('请至少选择一个推荐器');
      setStatus('error');
      return;
    }
    setStatus('running');
    setErrorMsg('');
    setResult(null);
    try {
      const expName = form.name.trim() || `exp_${Date.now()}`;
      const res = await runExperiment({ ...form, name: expName });
      setResult(res);
      setStatus('success');
    } catch (e: any) {
      setErrorMsg(e.message || '实验运行失败');
      setStatus('error');
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: Config Form */}
      <div className="bg-gray-800 rounded-xl p-6 space-y-5">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Play className="w-5 h-5 text-blue-400" />
          实验配置
        </h2>

        {/* Experiment Name */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">实验名称（可选）</label>
          <input
            type="text"
            value={form.name}
            onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
            placeholder="留空则自动生成"
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Dataset */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">数据集</label>
          <select
            value={form.datasetId}
            onChange={e => setForm(p => ({ ...p, datasetId: e.target.value }))}
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
          >
            {DATASETS.map(d => (
              <option key={d.id} value={d.id}>{d.label}</option>
            ))}
          </select>
        </div>

        {/* Recommenders */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">推荐器（可多选）</label>
          <div className="space-y-2">
            {RECOMMENDERS.map(r => (
              <label key={r.id} className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={form.recommenders.includes(r.id)}
                  onChange={() => toggleRecommender(r.id)}
                  className="w-4 h-4 accent-blue-500"
                />
                <div>
                  <span className="text-sm text-white font-medium">{r.label}</span>
                  <span className="text-xs text-gray-400 ml-2">{r.desc}</span>
                </div>
              </label>
            ))}
          </div>
          {form.recommenders.length < 1 && (
            <p className="text-xs text-red-400 mt-1">请至少选择一个推荐器</p>
          )}
        </div>

        {/* Platform */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">平台</label>
          <select
            value={form.platform}
            onChange={e => setForm(p => ({ ...p, platform: e.target.value as any }))}
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
          >
            {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        {/* Steps / Seed / AgentCount */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Steps</label>
            <input
              type="number"
              min={1} max={100}
              value={form.steps}
              onChange={e => setForm(p => ({ ...p, steps: parseInt(e.target.value) || 15 }))}
              className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Seed</label>
            <input
              type="number"
              value={form.seed}
              onChange={e => setForm(p => ({ ...p, seed: parseInt(e.target.value) || 42 }))}
              className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Agents</label>
            <input
              type="number"
              min={1} max={100}
              value={form.agentCount}
              onChange={e => setForm(p => ({ ...p, agentCount: parseInt(e.target.value) || 10 }))}
              className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Run Button */}
        <button
          onClick={handleRun}
          disabled={status === 'running' || form.recommenders.length < 1}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg px-4 py-3 font-medium transition-colors"
        >
          {status === 'running' ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> 运行中...</>
          ) : (
            <><Play className="w-4 h-4" /> 运行实验</>
          )}
        </button>

        {/* Error */}
        {status === 'error' && (
          <div className="flex items-start gap-2 bg-red-900/30 border border-red-700 rounded-lg p-3">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-300">{errorMsg}</p>
          </div>
        )}
      </div>

      {/* Right: Result Summary */}
      <div className="bg-gray-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
          <CheckCircle2 className="w-5 h-5 text-green-400" />
          实验结果摘要
        </h2>

        {status === 'idle' && (
          <div className="flex flex-col items-center justify-center h-48 text-gray-500">
            <Play className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">配置参数后点击"运行实验"</p>
          </div>
        )}

        {status === 'running' && (
          <div className="flex flex-col items-center justify-center h-48 text-gray-400">
            <Loader2 className="w-12 h-12 mb-3 animate-spin text-blue-400" />
            <p className="text-sm">实验运行中，请稍候...</p>
            <p className="text-xs text-gray-500 mt-1">预计 10~30 秒</p>
          </div>
        )}

        {status === 'error' && !result && (
          <div className="flex flex-col items-center justify-center h-48 text-gray-500">
            <AlertCircle className="w-12 h-12 mb-3 text-red-400 opacity-60" />
            <p className="text-sm text-red-300">实验运行失败</p>
          </div>
        )}

        {status === 'success' && result && (
          <div className="space-y-4">
            {/* Experiment ID */}
            <div className="bg-gray-700/50 rounded-lg p-3">
              <p className="text-xs text-gray-400">Experiment ID</p>
              <p className="text-sm text-white font-mono truncate">{result.experimentId}</p>
            </div>

            {/* Config Summary */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="bg-gray-700/50 rounded-lg p-2">
                <p className="text-xs text-gray-400">数据集</p>
                <p className="text-white truncate">{result.datasetId}</p>
              </div>
              <div className="bg-gray-700/50 rounded-lg p-2">
                <p className="text-xs text-gray-400">推荐器</p>
                <p className="text-white truncate">{result.recommenders?.join(', ')}</p>
              </div>
            </div>

            {/* Per-recommender metrics */}
            {result.runs?.map(run => (
              <div key={run.recommender} className="bg-gray-700/50 rounded-lg p-3 space-y-2">
                <p className="text-sm font-semibold text-blue-300 capitalize">{run.recommender}</p>
                <div className="grid grid-cols-2 gap-2">
                  <MetricCard label="极化指数" value={run.metrics.polarization_final?.toFixed(4)} />
                  <MetricCard label="羊群指数" value={run.metrics.herd_index_final?.toFixed(4)} />
                  <MetricCard label="平均速度" value={run.metrics.velocity_avg?.toFixed(4)} />
                  <MetricCard label="总帖子数" value={String(run.metrics.total_posts)} />
                </div>
              </div>
            ))}

            {/* Toggle raw JSON */}
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
            >
              {showDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {showDetails ? '收起' : '查看'} 原始 JSON
            </button>
            {showDetails && (
              <pre className="bg-gray-900 rounded-lg p-3 text-xs text-gray-300 overflow-auto max-h-48">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value?: string }) {
  return (
    <div className="bg-gray-800 rounded p-2">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm text-white font-mono">{value ?? '—'}</p>
    </div>
  );
}
