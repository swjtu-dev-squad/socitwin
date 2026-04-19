import React, { useState, useEffect } from 'react'
import {
  Settings as SettingsIcon,
  Database,
  Cpu,
  Save,
  RefreshCw,
  Trash2,
  AlertTriangle,
  Plus,
  Edit2,
  X,
  Key,
} from 'lucide-react'
import { Card, Button, Input, Badge } from '@/components/ui'
import { toast } from 'sonner'

interface ModelConfig {
  id: string
  name: string
  apiEndpoint: string
  apiKey: string
  isDefault: boolean
}

const defaultModelConfigs: ModelConfig[] = [
  {
    id: '1',
    name: 'GPT-4o-mini (推荐)',
    apiEndpoint: 'https://api.openai.com/v1',
    apiKey: '',
    isDefault: true,
  },
  {
    id: '2',
    name: 'GPT-4o (高性能)',
    apiEndpoint: 'https://api.openai.com/v1',
    apiKey: '',
    isDefault: false,
  },
  {
    id: '3',
    name: 'Claude 3.5 Sonnet',
    apiEndpoint: 'https://api.anthropic.com/v1',
    apiKey: '',
    isDefault: false,
  },
  {
    id: '4',
    name: 'DeepSeek-V3',
    apiEndpoint: 'https://api.deepseek.com/v1',
    apiKey: '',
    isDefault: false,
  },
]

export default function Settings() {
  const [isSaving, setIsSaving] = useState(false)
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null)
  const [isAddingNew, setIsAddingNew] = useState(false)
  const [newConfig, setNewConfig] = useState<Omit<ModelConfig, 'id'>>({
    name: '',
    apiEndpoint: '',
    apiKey: '',
    isDefault: false,
  })

  // 从 localStorage 加载配置
  useEffect(() => {
    const savedConfigs = localStorage.getItem('socitwin_model_configs')
    if (savedConfigs) {
      try {
        setModelConfigs(JSON.parse(savedConfigs))
      } catch (e) {
        console.error('Failed to load model configs:', e)
        // 使用默认配置
        setModelConfigs(defaultModelConfigs)
      }
    } else {
      // 如果没有保存的配置，使用默认配置
      setModelConfigs(defaultModelConfigs)
    }
  }, [])

  // 保存配置到 localStorage
  const saveConfigsToStorage = (configs: ModelConfig[]) => {
    localStorage.setItem('socitwin_model_configs', JSON.stringify(configs))
  }

  const handleSave = () => {
    setIsSaving(true)
    // 保存到 localStorage
    saveConfigsToStorage(modelConfigs)
    setTimeout(() => {
      setIsSaving(false)
      toast.success('模型配置已保存')
    }, 1000)
  }

  const handleAddConfig = () => {
    if (!newConfig.name.trim() || !newConfig.apiEndpoint.trim()) {
      toast.error('请填写模型名称和API端点')
      return
    }

    const newId = Date.now().toString()
    const configToAdd: ModelConfig = {
      id: newId,
      ...newConfig,
    }

    // 如果设置为默认，先取消其他默认设置
    if (newConfig.isDefault) {
      const updatedConfigs = modelConfigs.map((config: ModelConfig) => ({
        ...config,
        isDefault: false,
      }))
      setModelConfigs([...updatedConfigs, configToAdd])
    } else {
      setModelConfigs([...modelConfigs, configToAdd])
    }

    // 重置表单
    setNewConfig({
      name: '',
      apiEndpoint: '',
      apiKey: '',
      isDefault: false,
    })
    setIsAddingNew(false)
    toast.success('模型配置已添加')
  }

  const handleEditConfig = (config: ModelConfig) => {
    setEditingConfig(config)
  }

  const handleUpdateConfig = () => {
    if (!editingConfig) return

    if (!editingConfig.name.trim() || !editingConfig.apiEndpoint.trim()) {
      toast.error('请填写模型名称和API端点')
      return
    }

    const updatedConfigs = modelConfigs.map((config: ModelConfig) =>
      config.id === editingConfig.id
        ? editingConfig
        : editingConfig.isDefault
          ? { ...config, isDefault: false }
          : config
    )
    setModelConfigs(updatedConfigs)
    setEditingConfig(null)
    toast.success('模型配置已更新')
  }

  const handleDeleteConfig = (id: string) => {
    const configToDelete = modelConfigs.find((c: ModelConfig) => c.id === id)
    if (configToDelete?.isDefault) {
      toast.error('不能删除默认模型配置')
      return
    }

    const updatedConfigs = modelConfigs.filter((config: ModelConfig) => config.id !== id)
    setModelConfigs(updatedConfigs)
    toast.success('模型配置已删除')
  }

  const handleSetDefault = (id: string) => {
    const updatedConfigs = modelConfigs.map((config: ModelConfig) => ({
      ...config,
      isDefault: config.id === id,
    }))
    setModelConfigs(updatedConfigs)
    toast.success('默认模型已更新')
  }

  const getDefaultModel = () => {
    return modelConfigs.find((config: ModelConfig) => config.isDefault) || modelConfigs[0]
  }

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
              <Button onClick={() => setIsAddingNew(true)} variant="outline" className="gap-2">
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
                {modelConfigs.map(config => (
                  <div
                    key={config.id}
                    className={`p-6 border rounded-2xl transition-all ${config.isDefault ? 'border-accent bg-accent/5' : 'border-border-default bg-bg-primary'}`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="space-y-2">
                        <div className="flex items-center gap-3">
                          <h4 className="text-base font-bold text-text-primary">{config.name}</h4>
                          {config.isDefault && (
                            <Badge className="bg-accent/10 text-accent border-accent/20">
                              默认
                            </Badge>
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
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNewConfig({ ...newConfig, name: e.target.value })
                    }
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
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNewConfig({ ...newConfig, apiEndpoint: e.target.value })
                    }
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
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNewConfig({ ...newConfig, apiKey: e.target.value })
                    }
                    placeholder="输入API密钥（可选）"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="flex items-center space-x-3 pt-8">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={newConfig.isDefault}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNewConfig({ ...newConfig, isDefault: e.target.checked })
                    }
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
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setEditingConfig({ ...editingConfig, name: e.target.value })
                    }
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    API 端点
                  </label>
                  <Input
                    value={editingConfig.apiEndpoint}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setEditingConfig({ ...editingConfig, apiEndpoint: e.target.value })
                    }
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
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setEditingConfig({ ...editingConfig, apiKey: e.target.value })
                    }
                    placeholder="输入API密钥（可选）"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>
                <div className="flex items-center space-x-3 pt-8">
                  <input
                    type="checkbox"
                    id="editIsDefault"
                    checked={editingConfig.isDefault}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setEditingConfig({ ...editingConfig, isDefault: e.target.checked })
                    }
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
                    const selectedId = e.target.value
                    if (selectedId) {
                      handleSetDefault(selectedId)
                    }
                  }}
                >
                  {modelConfigs.map(config => (
                    <option key={config.id} value={config.id}>
                      {config.name} {config.isDefault ? '(默认)' : ''}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-text-tertiary mt-2">选择默认模型用于所有推理任务</p>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                  默认模型 API 端点
                </label>
                <div className="p-3 bg-bg-primary border border-border-default rounded-xl text-sm text-text-secondary font-mono">
                  {getDefaultModel()?.apiEndpoint || '未设置'}
                </div>
                <p className="text-xs text-text-tertiary mt-2">当前默认模型的API端点地址</p>
              </div>
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
            <Button
              variant="outline"
              className="h-14 justify-start px-6 gap-4 rounded-2xl border-border-default"
            >
              <Database className="w-5 h-5 text-text-tertiary" />
              <div className="text-left">
                <p className="text-sm font-bold">备份 simulation.db</p>
                <p className="text-[10px] text-text-tertiary">下载当前所有模拟状态</p>
              </div>
            </Button>
            <Button
              variant="outline"
              className="h-14 justify-start px-6 gap-4 rounded-2xl border-border-default"
            >
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
  )
}
