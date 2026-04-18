import React from 'react'
import { Slider } from '@/components/ui'
import type { PlatformStrategy } from '@/lib/labTypes'

interface LabParamSettingsProps {
  platform: PlatformStrategy
  onUpdate: (platformId: string, paramKey: keyof PlatformStrategy['params'], value: number) => void
}

export const LabParamSettings: React.FC<LabParamSettingsProps> = ({ platform, onUpdate }) => {
  return (
    <div className="p-4 bg-bg-primary rounded-xl border border-border-default space-y-4">
      <div className="flex justify-between items-center">
        <h4 className="font-bold text-accent">{platform.name} 参数微调</h4>
        <span className="text-[10px] text-text-muted">模型版本: v2.5-Industrial</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <ParamSlider
          label="兴趣匹配度"
          value={platform.params.interestWeight}
          onChange={(v: number) => onUpdate(platform.id, 'interestWeight', v)}
        />
        <ParamSlider
          label="社交关联度"
          value={platform.params.socialWeight}
          onChange={(v: number) => onUpdate(platform.id, 'socialWeight', v)}
        />
        <ParamSlider
          label="时效性权重"
          value={platform.params.recencyWeight}
          onChange={(v: number) => onUpdate(platform.id, 'recencyWeight', v)}
        />
        <ParamSlider
          label="探索/破圈率"
          value={platform.params.explorationRate}
          onChange={(v: number) => onUpdate(platform.id, 'explorationRate', v)}
        />
      </div>
    </div>
  )
}

function ParamSlider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] uppercase font-bold">
        <label className="text-text-secondary">{label}</label>
        <span className="text-accent">{value.toFixed(2)}</span>
      </div>
      <Slider
        value={[value]}
        min={0}
        max={1}
        step={0.01}
        onValueChange={v => onChange(v[0])}
        className="py-2"
      />
    </div>
  )
}
