import { useState } from 'react';
import { Settings as SettingsIcon, Database, Shield, Cpu, Save, RefreshCw, Trash2, AlertTriangle } from 'lucide-react';
import { Card, Button, Input, Badge } from '@/components/ui';
import { toast } from 'sonner';

export default function Settings() {
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      toast.success('设置已保存');
    }, 1000);
  };

  return (
    <div className="px-6 lg:px-12 py-10 space-y-8 max-w-5xl mx-auto">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <SettingsIcon className="w-10 h-10 text-accent" />
            系统设置
          </h1>
          <p className="text-text-tertiary mt-1">管理 OASIS 引擎核心参数、模型配置与数据运维</p>
        </div>
        <Button onClick={handleSave} disabled={isSaving} className="h-11 px-8 gap-2">
          {isSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          保存更改
        </Button>
      </header>

      <div className="grid grid-cols-1 gap-8">
        <Card className="p-8 bg-bg-secondary border-border-default space-y-8">
          <div className="flex items-center justify-between border-b border-border-default pb-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Cpu className="w-5 h-5 text-blue-400" />
              LLM 推理引擎
            </h2>
            <Badge variant="outline" className="text-accent border-accent/20 bg-accent/5">连接正常</Badge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">默认推理模型</label>
              <select className="w-full h-11 bg-bg-primary border border-border-default rounded-xl px-4 text-sm">
                <option>GPT-4o-mini (推荐)</option>
                <option>GPT-4o (高性能)</option>
                <option>Claude 3.5 Sonnet</option>
                <option>DeepSeek-V3</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">API Endpoint</label>
              <Input defaultValue="https://api.openai.com/v1" className="bg-bg-primary border-border-default rounded-xl" />
            </div>
          </div>
        </Card>

        <Card className="p-8 bg-bg-secondary border-border-default space-y-8">
          <div className="flex items-center justify-between border-b border-border-default pb-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Database className="w-5 h-5 text-accent" />
              数据存储与运维
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Button variant="outline" className="h-14 justify-start px-6 gap-4 rounded-2xl border-border-default">
              <Database className="w-5 h-5 text-text-tertiary" />
              <div className="text-left">
                <p className="text-sm font-bold">备份 simulation.db</p>
                <p className="text-[10px] text-text-tertiary">下载当前所有模拟状态</p>
              </div>
            </Button>
            <Button variant="outline" className="h-14 justify-start px-6 gap-4 rounded-2xl border-border-default">
              <RefreshCw className="w-5 h-5 text-text-tertiary" />
              <div className="text-left">
                <p className="text-sm font-bold">重建索引</p>
                <p className="text-[10px] text-text-tertiary">优化 SQLite 查询性能</p>
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
            <Button variant="destructive" className="w-full h-12 rounded-xl font-bold gap-2">
              <Trash2 className="w-4 h-4" />
              清空当前所有模拟数据
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
