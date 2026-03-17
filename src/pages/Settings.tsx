import { useState } from 'react';
import { DatasetImport } from '@/components/DatasetImport';
import { 
  Card, 
  Button, 
  Input, 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue, 
  Badge,
  Switch
} from '@/components/ui';
import { 
  Settings as SettingsIcon, 
  Database, 
  Shield, 
  Cpu, 
  History, 
  Trash2, 
  Save, 
  Cloud, 
  HardDrive,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Share2
} from 'lucide-react';

export default function Settings() {
  const [isSaving, setIsSaving] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => setIsSaving(false), 1500);
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-10 pb-20">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <SettingsIcon className="w-10 h-10 text-accent" />
            系统设置
          </h1>
          <p className="text-text-tertiary mt-1">管理 OASIS 引擎核心参数、模型配置与数据运维</p>
        </div>
        <Button 
          onClick={handleSave}
          disabled={isSaving}
          className="bg-accent hover:bg-accent-hover rounded-xl h-11 px-8 font-bold gap-2"
        >
          {isSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {isSaving ? '保存中...' : '保存更改'}
        </Button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Model & API */}
        <div className="lg:col-span-2 space-y-8">
          <Card className="bg-bg-secondary border-border-default p-8 space-y-8">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Cpu className="w-5 h-5 text-blue-400" />
                LLM 推理引擎
              </h2>
              <Badge variant="outline" className="text-[10px] border-accent/20 text-accent bg-accent/5">
                连接正常
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-3">
                <label className="text-xs font-bold text-text-tertiary uppercase tracking-widest">默认推理模型</label>
                <Select defaultValue="gpt-4o-mini">
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-bg-secondary border-border-default">
                    <SelectItem value="gpt-4o-mini">GPT-4o-mini (推荐 · 极速)</SelectItem>
                    <SelectItem value="gpt-4o">GPT-4o (高性能 · 深度推理)</SelectItem>
                    <SelectItem value="o1-preview">OpenAI o1-preview (逻辑强化)</SelectItem>
                    <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
                    <SelectItem value="deepseek-v3">DeepSeek-V3 (国产最强)</SelectItem>
                    <SelectItem value="vllm-local">vLLM 本地集群 (私有化)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-text-muted italic">推荐使用 mini 模型以平衡成本与速度</p>
              </div>
              <div className="space-y-3">
                <label className="text-xs font-bold text-text-tertiary uppercase tracking-widest">API 密钥 (GEMINI_API_KEY)</label>
                <div className="relative">
                  <Input 
                    type="password" 
                    value="sk-••••••••••••••••••••" 
                    readOnly
                    className="bg-bg-primary border-border-default h-12 rounded-xl pr-10 font-mono text-xs text-text-secondary"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <CheckCircle2 className="w-4 h-4 text-accent" />
                  </div>
                </div>
                <p className="text-[10px] text-text-muted italic">密钥已通过环境变量注入，状态：有效</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-bg-primary/50 border border-border-default rounded-2xl group hover:border-border-strong transition-colors">
                <div className="flex gap-4 items-center">
                  <div className="w-10 h-10 rounded-xl bg-bg-secondary flex items-center justify-center">
                    <Shield className="w-5 h-5 text-text-tertiary" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-text-primary">每 Agent 独立模型配置</p>
                    <p className="text-[11px] text-text-tertiary">允许为不同性格的 Agent 分配特定的微调模型</p>
                  </div>
                </div>
                <Switch defaultChecked />
              </div>

              <div className="flex items-center justify-between p-4 bg-bg-primary/50 border border-border-default rounded-2xl group hover:border-border-strong transition-colors">
                <div className="flex gap-4 items-center">
                  <div className="w-10 h-10 rounded-xl bg-bg-secondary flex items-center justify-center">
                    <Cloud className="w-5 h-5 text-text-tertiary" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-text-primary">云端同步与备份</p>
                    <p className="text-[11px] text-text-tertiary">自动将模拟结果同步至 CAMEL-AI 云端存储</p>
                  </div>
                </div>
                <Switch />
              </div>
            </div>
          </Card>

          <Card className="bg-bg-secondary border-border-default p-8 space-y-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Database className="w-5 h-5 text-accent" />
              自定义数据集导入
            </h2>
            <DatasetImport />
          </Card>

          <Card className="bg-bg-secondary border-border-default p-8 space-y-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Database className="w-5 h-5 text-accent" />
              数据运维与导出
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Button variant="outline" className="rounded-xl h-14 border-border-default justify-start px-6 gap-4 hover:bg-bg-tertiary transition-all">
                <HardDrive className="w-5 h-5 text-text-tertiary" />
                <div className="text-left">
                  <p className="text-xs font-bold">备份 simulation.db</p>
                  <p className="text-[10px] text-text-tertiary">下载当前所有模拟状态</p>
                </div>
              </Button>
              <Button variant="outline" className="rounded-xl h-14 border-border-default justify-start px-6 gap-4 hover:bg-bg-tertiary transition-all">
                <Share2 className="w-5 h-5 text-text-tertiary" />
                <div className="text-left">
                  <p className="text-xs font-bold">导出 HF 数据集</p>
                  <p className="text-[10px] text-text-tertiary">转换为 HuggingFace 格式</p>
                </div>
              </Button>
            </div>
            
            <div className="p-6 bg-rose-500/5 border border-rose-500/20 rounded-2xl space-y-4">
              <div className="flex items-center gap-3 text-rose-500">
                <AlertTriangle className="w-5 h-5" />
                <h4 className="text-sm font-bold uppercase tracking-widest">危险区域</h4>
              </div>
              <p className="text-xs text-text-tertiary leading-relaxed">
                清空数据将永久删除所有 Agent 轨迹、社交网络关系及历史日志。此操作不可撤销。
              </p>
              {showResetConfirm ? (
                <div className="flex gap-3 animate-in fade-in slide-in-from-top-2">
                  <Button 
                    variant="destructive" 
                    className="flex-1 rounded-xl h-10 font-bold"
                    onClick={() => setShowResetConfirm(false)}
                  >确认清空</Button>
                  <Button 
                    variant="outline" 
                    className="flex-1 rounded-xl h-10 border-border-default font-bold"
                    onClick={() => setShowResetConfirm(false)}
                  >取消</Button>
                </div>
              ) : (
                <Button 
                  variant="destructive" 
                  className="w-full rounded-xl h-10 font-bold gap-2"
                  onClick={() => setShowResetConfirm(true)}
                >
                  <Trash2 className="w-4 h-4" />
                  清空当前所有模拟数据
                </Button>
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: History & Stats */}
        <div className="space-y-8">
          <Card className="bg-bg-secondary border-border-default p-8 space-y-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <History className="w-5 h-5 text-yellow-400" />
              最近模拟
            </h2>
            <div className="space-y-4">
              {[
                { date: '2026-02-22 14:30', config: 'Reddit + Hot-score', agents: '10k', pol: '0.87' },
                { date: '2026-02-21 09:15', config: 'X + TwHIN', agents: '5k', pol: '0.62' },
                { date: '2026-02-20 18:45', config: 'Stress Test', agents: '50k', pol: '0.94' },
              ].map((history, i) => (
                <div key={i} className="flex items-center justify-between p-4 bg-bg-primary/50 border border-border-default rounded-2xl group hover:border-border-strong transition-colors cursor-pointer">
                  <div className="space-y-1">
                    <p className="text-xs font-bold text-text-primary">{history.date}</p>
                    <div className="flex items-center gap-2 text-[10px] text-text-muted">
                      <span>{history.agents} Agents</span>
                      <span>·</span>
                      <span className="text-rose-500 font-bold">极化 {history.pol}</span>
                    </div>
                  </div>
                  <RefreshCw className="w-4 h-4 text-text-muted group-hover:text-accent transition-colors" />
                </div>
              ))}
            </div>
            <Button variant="ghost" className="w-full text-xs text-text-muted hover:text-text-secondary">查看完整历史记录</Button>
          </Card>

          <Card className="bg-bg-secondary border-border-default p-8 space-y-4 text-center">
            <div className="w-16 h-16 bg-bg-primary rounded-full flex items-center justify-center mx-auto border border-border-default mb-2">
              <SettingsIcon className="w-8 h-8 text-text-muted" />
            </div>
            <div>
              <p className="text-xs font-bold text-text-secondary">OASIS Engine v0.2.5</p>
              <p className="text-[10px] text-text-muted mt-1">Build: 20260222-STABLE</p>
            </div>
            <Button variant="outline" className="w-full rounded-xl border-border-default text-[10px] h-9">检查更新</Button>
          </Card>
        </div>
      </div>

      <footer className="text-center space-y-2 py-10 border-t border-border-default">
        <p className="text-[10px] text-text-muted uppercase tracking-widest font-bold">© CAMEL-AI 2026 · All Rights Reserved</p>
      </footer>
    </div>
  );
}
