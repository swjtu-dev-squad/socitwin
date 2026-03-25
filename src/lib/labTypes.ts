// 5大平台策略参数定义
export interface PlatformStrategy {
  id: 'tiktok' | 'xiaohongshu' | 'pinterest' | 'reddit' | 'twitter';
  name: string;
  params: {
    interestWeight: number;    // 兴趣个性化权重
    socialWeight: number;      // 社交关系权重
    recencyWeight: number;     // 时效性/新鲜度权重
    qualityWeight: number;     // 内容质量权重
    explorationRate: number;   // 破圈/探索率
  };
}

// 推演任务定义
export interface InferenceTask {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'failed';
  progress: number;
  datasetId: string;
  baselineId: string;         // 参照基准ID (真实历史数据)
  platformConfigs: PlatformStrategy[];
  metrics: {
    currentPolarization: number;
    baselinePolarization: number;
    fitScore: number;         // 拟合度 (0-100%)
    biasValue: number;        // 预测偏差值
  };
  stepsTrace: Array<{
    step: number;
    simValue: number;         // 模拟值
    baseValue: number;        // 基准值
  }>;
}
