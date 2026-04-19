import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Database, Cpu, Save, RefreshCw, Trash2, AlertTriangle, Plus, Edit2, X, Key, Brain, Dice1 as Dice, GitBranch, Calendar, BarChart3, AlertCircle, Zap } from 'lucide-react';
import { Card, Button, Input, Badge, Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui';
import { toast } from 'sonner';
import { getBehaviorControllerStatus, getBehaviorStatistics, applyPresetConfig, getAvailableStrategies } from '@/lib/behaviorApi';
import type { BehaviorControllerStatus } from '@/lib/behaviorTypes';

interface ModelConfig {
  id: string;
  name: string;
  apiEndpoint: string;
  apiKey: string;
  isDefault: boolean;
}

const defaultModelConfigs: ModelConfig[] = [
  { id: '1', name: 'GPT-4o-mini (推荐)', apiEndpoint: 'https://api.openai.com/v1', apiKey: '', isDefault: true },
  { id: '2', name: 'GPT-4o (高性能)', apiEndpoint: 'https://api.openai.com/v1', apiKey: '', isDefault: false },
  { id: '3', name: 'Claude 3.5 Sonnet', apiEndpoint: 'https://api.anthropic.com/v1', apiKey: '', isDefault: false },
  { id: '4', name: 'DeepSeek-V3', apiEndpoint: 'https://api.deepseek.com/v1', apiKey: '', isDefault: false },
];

export default function Settings() {
  const [isSaving, setIsSaving] = useState(false);
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([]);
  const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newConfig, setNewConfig] = useState<Omit<ModelConfig, 'id'>>({
    name: '',
    apiEndpoint: '',
    apiKey: '',
    isDefault: false,
  });

  // 行为控制相关状态
  const [behaviorStatus, setBehaviorStatus] = useState<BehaviorControllerStatus | null>(null);
  const [behaviorStats, setBehaviorStats] = useState<any>(null);
  const [isLoadingBehavior, setIsLoadingBehavior] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [selectedPreset, setSelectedPreset] = useState('default');
  const [presetPlatform, setPresetPlatform] = useState<'twitter' | 'reddit'>('twitter');

  // 从 localStorage 加载配置
  useEffect(() => {
    const savedConfigs = localStorage.getItem('socitwin_model_configs');
    if (savedConfigs) {
      try {
        setModelConfigs(JSON.parse(savedConfigs));
      } catch (e) {
        console.error('Failed to load model configs:', e);
        // 使用默认配置
        setModelConfigs(defaultModelConfigs);
      }
    } else {
      // 如果没有保存的配置，使用默认配置
      setModelConfigs(defaultModelConfigs);
    }
  }, []);

  // 加载行为控制数据
  useEffect(() => {
    const loadBehaviorData = async () => {
      setIsLoadingBehavior(true);
      try {
        // 加载控制器状态
        const status = await getBehaviorControllerStatus();
        setBehaviorStatus(status);

        // 加载统计信息
        const stats = await getBehaviorStatistics();
        setBehaviorStats(stats);

        // 加载可用策略（暂未在界面使用）
        // const strategies = await getAvailableStrategies();
      } catch (error) {
        console.error('Failed to load behavior data:', error);
        toast.error('加载行为控制数据失败');
      } finally {
        setIsLoadingBehavior(false);
      }
    };

    loadBehaviorData();
  }, []);

  // 保存配置到 localStorage
  const saveConfigsToStorage = (configs: ModelConfig[]) => {
    localStorage.setItem('socitwin_model_configs', JSON.stringify(configs));
  };

  const handleSave = () => {
    setIsSaving(true);
    // 保存到 localStorage
    saveConfigsToStorage(modelConfigs);
    setTimeout(() => {
      setIsSaving(false);
      toast.success('模型配置已保存');
    }, 1000);
  };

  const handleAddConfig = () => {
    if (!newConfig.name.trim() || !newConfig.apiEndpoint.trim()) {
      toast.error('请填写模型名称和API端点');
      return;
    }

    const newId = Date.now().toString();
    const configToAdd: ModelConfig = {
      id: newId,
      ...newConfig,
    };

    // 如果设置为默认，先取消其他默认设置
    if (newConfig.isDefault) {
      const updatedConfigs = modelConfigs.map((config: ModelConfig) => ({
        ...config,
        isDefault: false,
      }));
      setModelConfigs([...updatedConfigs, configToAdd]);
    } else {
      setModelConfigs([...modelConfigs, configToAdd]);
    }

    // 重置表单
    setNewConfig({
      name: '',
      apiEndpoint: '',
      apiKey: '',
      isDefault: false,
    });
    setIsAddingNew(false);
    toast.success('模型配置已添加');
  };

  const handleEditConfig = (config: ModelConfig) => {
    setEditingConfig(config);
  };

  const handleUpdateConfig = () => {
    if (!editingConfig) return;

    if (!editingConfig.name.trim() || !editingConfig.apiEndpoint.trim()) {
      toast.error('请填写模型名称和API端点');
      return;
    }

    const updatedConfigs = modelConfigs.map((config: ModelConfig) =>
      config.id === editingConfig.id ? editingConfig :
      editingConfig.isDefault ? { ...config, isDefault: false } : config
    );
    setModelConfigs(updatedConfigs);
    setEditingConfig(null);
    toast.success('模型配置已更新');
  };

  const handleDeleteConfig = (id: string) => {
    const configToDelete = modelConfigs.find((c: ModelConfig) => c.id === id);
    if (configToDelete?.isDefault) {
      toast.error('不能删除默认模型配置');
      return;
    }

    const updatedConfigs = modelConfigs.filter((config: ModelConfig) => config.id !== id);
    setModelConfigs(updatedConfigs);
    toast.success('模型配置已删除');
  };

  const handleSetDefault = (id: string) => {
    const updatedConfigs = modelConfigs.map((config: ModelConfig) => ({
      ...config,
      isDefault: config.id === id,
    }));
    setModelConfigs(updatedConfigs);
    toast.success('默认模型已更新');
  };

  const getDefaultModel = () => {
    return modelConfigs.find((config: ModelConfig) => config.isDefault) || modelConfigs[0];
  };

  // 行为控制相关处理函数
  const handleApplyPreset = async () => {
    if (selectedAgentId === null) {
      toast.error('请选择智能体ID');
      return;
    }

    setIsLoadingBehavior(true);
    try {
      const response = await applyPresetConfig(selectedAgentId, selectedPreset, presetPlatform);
      if (response.success) {
        toast.success(`预设配置已应用到智能体 ${selectedAgentId}`);
        // 重新加载数据
        const status = await getBehaviorControllerStatus();
        setBehaviorStatus(status);
      } else {
        toast.error(`应用预设失败: ${response.error || response.message}`);
      }
    } catch (error) {
      console.error('Failed to apply preset:', error);
      toast.error('应用预设配置失败');
    } finally {
      setIsLoadingBehavior(false);
    }
  };

  const handleRefreshBehaviorData = async () => {
    setIsLoadingBehavior(true);
    try {
      // 重新加载所有行为控制数据
      const [status, stats] = await Promise.all([
        getBehaviorControllerStatus(),
        getBehaviorStatistics()
      ]);

      setBehaviorStatus(status);
      setBehaviorStats(stats);
      toast.success('行为控制数据已刷新');
    } catch (error) {
      console.error('Failed to refresh behavior data:', error);
      toast.error('刷新行为控制数据失败');
    } finally {
      setIsLoadingBehavior(false);
    }
  };

  const formatStrategyPercentage = (percentage: number) => {
    return `${percentage.toFixed(1)}%`;
  };

  return (
    <div className="px-6 lg:px-12 py-10 space-y-8 max-w-5xl mx-auto">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <SettingsIcon className="w-10 h-10 text-accent" />
            系统设置
          </h1>
          <p className="text-text-tertiary mt-1">管理 Socitwin 引擎核心参数、模型配置与数据运维</p>
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
              LLM 推理引擎配置
            </h2>
            <Badge variant="outline" className="text-accent border-accent/20 bg-accent/5">
              {modelConfigs.length} 个模型配置
            </Badge>
          </div>

          {/* 模型配置列表 */}
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-text-primary">模型配置列表</h3>
              <Button
                onClick={() => setIsAddingNew(true)}
                variant="outline"
                className="gap-2"
              >
                <Plus className="w-4 h-4" />
                添加新模型
              </Button>
            </div>

            {modelConfigs.length === 0 ? (
              <div className="text-center py-12 border border-border-default rounded-2xl">
                <Cpu className="w-12 h-12 mx-auto text-text-tertiary mb-4" />
                <p className="text-text-secondary">暂无模型配置</p>
                <p className="text-xs text-text-tertiary mt-2">点击右上角"添加新模型"开始配置</p>
              </div>
            ) : (
              <div className="space-y-4">
                {modelConfigs.map((config) => (
                  <div
                    key={config.id}
                    className={`p-6 border rounded-2xl transition-all ${config.isDefault ? 'border-accent bg-accent/5' : 'border-border-default bg-bg-primary'}`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="space-y-2">
                        <div className="flex items-center gap-3">
                          <h4 className="text-base font-bold text-text-primary">{config.name}</h4>
                          {config.isDefault && (
                            <Badge className="bg-accent/10 text-accent border-accent/20">默认</Badge>
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <Key className="w-3 h-3 text-text-tertiary" />
                            <p className="text-xs text-text-secondary font-mono truncate">
                              {config.apiEndpoint}
                            </p>
                          </div>
                          <p className="text-xs text-text-tertiary">
                            API密钥: {config.apiKey ? '••••••••' : '未设置'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!config.isDefault && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSetDefault(config.id)}
                            className="text-xs"
                          >
                            设为默认
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditConfig(config)}
                          className="text-text-tertiary hover:text-text-primary"
                        >
                          <Edit2 className="w-3 h-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteConfig(config.id)}
                          className="text-text-tertiary hover:text-rose-500"
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 添加新模型表单 */}
          {isAddingNew && (
            <div className="p-6 border border-accent/20 bg-accent/5 rounded-2xl space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-text-primary">添加新模型配置</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsAddingNew(false)}
                  className="text-text-tertiary"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    模型名称
                  </label>
                  <Input
                    value={newConfig.name}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewConfig({...newConfig, name: e.target.value})}
                    placeholder="例如: GPT-4o"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    API 端点
                  </label>
                  <Input
                    value={newConfig.apiEndpoint}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewConfig({...newConfig, apiEndpoint: e.target.value})}
                    placeholder="例如: https://api.openai.com/v1"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    API 密钥
                  </label>
                  <Input
                    type="password"
                    value={newConfig.apiKey}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewConfig({...newConfig, apiKey: e.target.value})}
                    placeholder="输入API密钥（可选）"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="flex items-center space-x-3 pt-8">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={newConfig.isDefault}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewConfig({...newConfig, isDefault: e.target.checked})}
                    className="w-4 h-4 accent-accent"
                  />
                  <label htmlFor="isDefault" className="text-sm text-text-secondary">
                    设为默认模型
                  </label>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button variant="outline" onClick={() => setIsAddingNew(false)}>
                  取消
                </Button>
                <Button onClick={handleAddConfig} className="gap-2">
                  <Plus className="w-4 h-4" />
                  添加模型
                </Button>
              </div>
            </div>
          )}

          {/* 编辑模型表单 */}
          {editingConfig && (
            <div className="p-6 border border-blue-500/20 bg-blue-500/5 rounded-2xl space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-text-primary">编辑模型配置</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditingConfig(null)}
                  className="text-text-tertiary"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    模型名称
                  </label>
                  <Input
                    value={editingConfig.name}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditingConfig({...editingConfig, name: e.target.value})}
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    API 端点
                  </label>
                  <Input
                    value={editingConfig.apiEndpoint}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditingConfig({...editingConfig, apiEndpoint: e.target.value})}
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    API 密钥
                  </label>
                  <Input
                    type="password"
                    value={editingConfig.apiKey}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditingConfig({...editingConfig, apiKey: e.target.value})}
                    placeholder="输入API密钥（可选）"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="flex items-center space-x-3 pt-8">
                  <input
                    type="checkbox"
                    id="editIsDefault"
                    checked={editingConfig.isDefault}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditingConfig({...editingConfig, isDefault: e.target.checked})}
                    className="w-4 h-4 accent-accent"
                  />
                  <label htmlFor="editIsDefault" className="text-sm text-text-secondary">
                    设为默认模型
                  </label>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button variant="outline" onClick={() => setEditingConfig(null)}>
                  取消
                </Button>
                <Button onClick={handleUpdateConfig} className="gap-2">
                  <Save className="w-4 h-4" />
                  保存更改
                </Button>
              </div>
            </div>
          )}

          {/* 默认模型选择器 */}
          <div className="pt-6 border-t border-border-default">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                  当前默认推理模型
                </label>
                <select
                  className="w-full h-11 bg-bg-primary border border-border-default rounded-xl px-4 text-sm"
                  value={getDefaultModel()?.id || ''}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                    const selectedId = e.target.value;
                    if (selectedId) {
                      handleSetDefault(selectedId);
                    }
                  }}
                >
                  {modelConfigs.map((config) => (
                    <option key={config.id} value={config.id}>
                      {config.name} {config.isDefault ? '(默认)' : ''}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-text-tertiary mt-2">
                  选择默认模型用于所有推理任务
                </p>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                  默认模型 API 端点
                </label>
                <div className="p-3 bg-bg-primary border border-border-default rounded-xl text-sm text-text-secondary font-mono">
                  {getDefaultModel()?.apiEndpoint || '未设置'}
                </div>
                <p className="text-xs text-text-tertiary mt-2">
                  当前默认模型的API端点地址
                </p>
              </div>
            </div>
          </div>
        </Card>

        

        <Card className="p-8 bg-bg-secondary border-border-default space-y-8">
          <div className="flex items-center justify-between border-b border-border-default pb-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Brain className="w-5 h-5 text-purple-500" />
              智能体行为控制配置
            </h2>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefreshBehaviorData}
                disabled={isLoadingBehavior}
                className="gap-2"
              >
                {isLoadingBehavior ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                刷新状态
              </Button>
              <Badge variant={behaviorStatus?.available ? "default" : "destructive"} className="text-xs">
                {behaviorStatus?.available ? "控制器在线" : "控制器离线"}
              </Badge>
            </div>
          </div>

          {isLoadingBehavior ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 animate-spin text-text-tertiary" />
              <p className="ml-3 text-text-secondary">加载行为控制数据...</p>
            </div>
          ) : behaviorStatus ? (
            <>
              {/* 控制器概览 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="p-6 border border-border-default bg-bg-primary rounded-2xl space-y-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${behaviorStatus.available ? 'bg-green-500' : 'bg-red-500'}`} />
                    <h3 className="text-base font-bold text-text-primary">控制器状态</h3>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-text-secondary">智能体配置数</span>
                      <span className="text-sm font-bold text-text-primary">{behaviorStatus.agent_config_count}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-text-secondary">OASIS连接</span>
                      <Badge variant={behaviorStatus.oasis_manager_connected ? "default" : "destructive"} className="text-xs">
                        {behaviorStatus.oasis_manager_connected ? "已连接" : "未连接"}
                      </Badge>
                    </div>
                  </div>
                </div>

                <div className="p-6 border border-border-default bg-bg-primary rounded-2xl space-y-3">
                  <div className="flex items-center gap-3">
                    <Zap className="w-5 h-5 text-blue-500" />
                    <h3 className="text-base font-bold text-text-primary">引擎可用性</h3>
                  </div>
                  <div className="space-y-2">
                    {behaviorStatus.engines && Object.entries(behaviorStatus.engines).map(([engine, available]) => (
                      <div key={engine} className="flex justify-between items-center">
                        <span className="text-sm text-text-secondary capitalize">{engine}</span>
                        <Badge variant={available ? "default" : "secondary"} className="text-xs">
                          {available ? "可用" : "不可用"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-6 border border-border-default bg-bg-primary rounded-2xl space-y-3">
                  <div className="flex items-center gap-3">
                    <BarChart3 className="w-5 h-5 text-green-500" />
                    <h3 className="text-base font-bold text-text-primary">策略分布</h3>
                  </div>
                  <div className="space-y-2">
                    {behaviorStatus.strategy_statistics && Object.entries(behaviorStatus.strategy_statistics).map(([strategy, stats]: [string, any]) => (
                      <div key={strategy} className="flex justify-between items-center">
                        <span className="text-sm text-text-secondary capitalize">{strategy.replace('_', ' ')}</span>
                        <span className="text-sm font-bold text-text-primary">{formatStrategyPercentage(stats.percentage || 0)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 配置管理 */}
              <div className="space-y-6">
                <h3 className="text-lg font-bold text-text-primary">预设配置应用</h3>

                <div className="p-6 border border-border-default bg-bg-primary rounded-2xl space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                        智能体ID
                      </label>
                      <Input
                        type="number"
                        value={selectedAgentId !== null ? selectedAgentId.toString() : ''}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSelectedAgentId(e.target.value ? parseInt(e.target.value) : null)}
                        placeholder="输入智能体ID"
                        className="bg-bg-primary border-border-default rounded-xl"
                      />
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                        预设配置
                      </label>
                      <select
                        value={selectedPreset}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedPreset(e.target.value)}
                        className="w-full h-11 bg-bg-primary border border-border-default rounded-xl px-4 text-sm focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
                      >
                        <option value="default">默认配置 (LLM自主决策)</option>
                        <option value="probabilistic">概率分布模型</option>
                        <option value="scheduled">时间线调度模型</option>
                        <option value="rule_based">规则引擎模型</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                        目标平台
                      </label>
                      <select
                        value={presetPlatform}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setPresetPlatform(e.target.value as 'twitter' | 'reddit')}
                        className="w-full h-11 bg-bg-primary border border-border-default rounded-xl px-4 text-sm focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
                      >
                        <option value="twitter">Twitter</option>
                        <option value="reddit">Reddit</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex justify-end gap-3">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setSelectedAgentId(null);
                        setSelectedPreset('default');
                        setPresetPlatform('twitter');
                      }}
                    >
                      重置
                    </Button>
                    <Button
                      onClick={handleApplyPreset}
                      disabled={selectedAgentId === null || isLoadingBehavior}
                      className="gap-2"
                    >
                      {isLoadingBehavior ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                      应用预设配置
                    </Button>
                  </div>
                </div>
              </div>

              {/* 详细统计 */}
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-text-primary">详细统计信息</h3>
                  <Badge variant="outline" className="text-text-tertiary">
                    最后更新: {behaviorStats ? new Date(behaviorStats.timestamp || Date.now()).toLocaleString() : '未加载'}
                  </Badge>
                </div>

                <div className="p-6 border border-border-default bg-bg-primary rounded-2xl">
                  <Tabs defaultValue="overview">
                    <TabsList className="grid w-full grid-cols-3 mb-4">
                      <TabsTrigger value="overview">概览</TabsTrigger>
                      <TabsTrigger value="strategies">策略统计</TabsTrigger>
                      <TabsTrigger value="engines">引擎状态</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="space-y-4">
                      {behaviorStats ? (
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-text-secondary">配置智能体总数</span>
                              <span className="text-sm font-bold text-text-primary">{behaviorStats.total_agents_with_config || 0}</span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-text-secondary">控制器初始化</span>
                              <Badge variant={behaviorStats.controller_initialized ? "default" : "destructive"} className="text-xs">
                                {behaviorStats.controller_initialized ? "已初始化" : "未初始化"}
                              </Badge>
                            </div>
                          </div>
                          <div className="space-y-2">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-text-secondary">数据更新时间</span>
                              <span className="text-sm text-text-tertiary">
                                {new Date(behaviorStats.timestamp || Date.now()).toLocaleTimeString()}
                              </span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-4 text-text-tertiary">
                          统计信息加载中...
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="strategies" className="space-y-4">
                      {behaviorStats && behaviorStats.strategy_statistics ? (
                        Object.entries(behaviorStats.strategy_statistics).map(([strategy, stats]: [string, any]) => (
                          <div key={strategy} className="flex items-center justify-between p-3 border border-border-default rounded-xl">
                            <div className="flex items-center gap-3">
                              <div className="w-2 h-2 rounded-full bg-accent" />
                              <span className="text-sm text-text-primary capitalize">{strategy.replace('_', ' ')}</span>
                            </div>
                            <div className="flex items-center gap-4">
                              <span className="text-xs text-text-tertiary">使用次数: {stats.count || 0}</span>
                              <span className="text-sm font-bold text-text-primary">{formatStrategyPercentage(stats.percentage || 0)}</span>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-4 text-text-tertiary">
                          策略统计数据加载中...
                        </div>
                      )}
                    </TabsContent>

                    <TabsContent value="engines" className="space-y-4">
                      {behaviorStatus ? (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="p-4 border border-border-default rounded-xl space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Dice className="w-4 h-4 text-green-500" />
                                <span className="text-sm font-bold">概率引擎</span>
                              </div>
                              <Badge variant={behaviorStatus.engines?.probabilistic ? "default" : "secondary"} className="text-xs">
                                {behaviorStatus.engines?.probabilistic ? "可用" : "不可用"}
                              </Badge>
                            </div>
                            <p className="text-xs text-text-tertiary">基于概率分布选择动作</p>
                          </div>

                          <div className="p-4 border border-border-default rounded-xl space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <GitBranch className="w-4 h-4 text-orange-500" />
                                <span className="text-sm font-bold">规则引擎</span>
                              </div>
                              <Badge variant={behaviorStatus.engines?.rule ? "default" : "secondary"} className="text-xs">
                                {behaviorStatus.engines?.rule ? "可用" : "不可用"}
                              </Badge>
                            </div>
                            <p className="text-xs text-text-tertiary">基于条件和规则触发动作</p>
                          </div>

                          <div className="p-4 border border-border-default rounded-xl space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Calendar className="w-4 h-4 text-purple-500" />
                                <span className="text-sm font-bold">调度引擎</span>
                              </div>
                              <Badge variant={behaviorStatus.engines?.scheduling ? "default" : "secondary"} className="text-xs">
                                {behaviorStatus.engines?.scheduling ? "可用" : "不可用"}
                              </Badge>
                            </div>
                            <p className="text-xs text-text-tertiary">按预定义时间线执行动作</p>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-4 text-text-tertiary">
                          引擎状态数据加载中...
                        </div>
                      )}
                    </TabsContent>
                  </Tabs>
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-12 border border-border-default rounded-2xl">
              <AlertCircle className="w-12 h-12 mx-auto text-text-tertiary mb-4" />
              <p className="text-text-secondary">无法加载行为控制数据</p>
              <p className="text-xs text-text-tertiary mt-2">请检查后端行为控制器是否正常运行</p>
              <Button
                variant="outline"
                className="mt-4 gap-2"
                onClick={handleRefreshBehaviorData}
              >
                <RefreshCw className="w-3 h-3" />
                重试加载
              </Button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
