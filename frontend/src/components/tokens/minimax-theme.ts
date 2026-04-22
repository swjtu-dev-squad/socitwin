/**
 * MiniMax设计系统令牌 - 深色主题版
 * 基于MiniMax DESIGN.md，适配深色主题
 */

// ============================================
// 颜色系统 - 深色主题
// ============================================

export const minimaxColors = {
  // 品牌色
  brand: {
    blue: '#1456f0', // 主品牌色
    primary500: '#3b82f6', // 标准蓝
    primary600: '#2563eb', // 悬停蓝
    light: '#60a5fa', // 亮蓝
    pink: '#ea5ec1', // 次级强调色
  },

  // 文本色 - 深色主题
  text: {
    primary: '#fafafa', // 主文本 - 近白
    secondary: '#a1a1aa', // 次文本 - 灰
    muted: '#71717a', // 静音文本
    dark: '#18181b', // 深色文本（按钮）
  },

  // 背景色 - 深色主题
  background: {
    primary: '#181e25', // 主背景 - 深色
    secondary: '#27272a', // 次背景 - 卡片
    tertiary: '#3f3f46', // 三级背景 - 输入框
    input: '#18181b', // 输入框深色
  },

  // 边框色
  border: {
    default: '#3f3f46', // 默认边框
    strong: '#52525b', // 强边框
    light: 'rgba(255, 255, 255, 0.05)', // 亮边框（分隔）
  },

  // 语义色
  semantic: {
    rose: '#f43f5e', // 警告/错误
    emerald: '#10b981', // 成功
    amber: '#f59e0b', // 警示
    blue: '#3b82f6', // 信息
  },
}

// ============================================
// 字体系统
// ============================================

export const minimaxFonts = {
  display: 'Outfit, "PingFang SC", "Microsoft YaHei", sans-serif',
  heading: 'Poppins, "PingFang SC", "Microsoft YaHei", sans-serif',
  body: '"DM Sans", "PingFang SC", "Microsoft YaHei", sans-serif',
  data: 'Roboto, "PingFang SC", "Microsoft YaHei", sans-serif',
}

// ============================================
// 字体大小规范（基于DESIGN.md）
// ============================================

export const minimaxFontSizes = {
  display: {
    hero: '5rem', // 80px - 英雄标题
    section: '1.94rem', // 31px - 章节标题
  },
  heading: {
    card: '1.75rem', // 28px - 卡片标题
    sub: '1.5rem', // 24px - 副标题
    feature: '1.13rem', // 18px - 功能标签
  },
  body: {
    large: '1.25rem', // 20px - 大正文
    base: '1rem', // 16px - 基础正文
    small: '0.88rem', // 14px - 小正文
  },
  ui: {
    buttonSmall: '0.81rem', // 13px - 小按钮
    caption: '0.81rem', // 13px - 说明文字
    label: '0.75rem', // 12px - 标签
    micro: '0.63rem', // 10px - 微文本
  },
}

// ============================================
// 字重规范
// ============================================

export const minimaxFontWeights = {
  display: 500, // 展示标题
  heading: 600, // 章节标题
  card: 500, // 卡片标题
  body: 400, // 正文
  medium: 500, // 中等强调
  bold: 600, // 强调
  strong: 700, // 强强调
}

// ============================================
// 行高规范
// ============================================

export const minimaxLineHeights = {
  tight: 1.1, // 展示标题
  normal: 1.5, // 大多数文本
  relaxed: 1.7, // 说明文字
}

// ============================================
// 间距系统（8px基准）
// ============================================

export const minimaxSpacing = {
  xs: '4px', // 0.5x
  sm: '8px', // 1x
  md: '16px', // 2x
  lg: '24px', // 3x
  xl: '32px', // 4x
  '2xl': '48px', // 6x
  '3xl': '64px', // 8x
}

// ============================================
// 圆角系统
// ============================================

export const minimaxRadius = {
  xs: '4px', // 极小圆角 - 标签
  sm: '8px', // 标准按钮
  md: '12px', // 中等卡片
  lg: '16px', // 大卡片
  xl: '20px', // 超大卡片
  '2xl': '24px', // 产品卡片
  pill: '9999px', // Pill按钮
}

// ============================================
// 阴影系统 - 深色环境优化
// ============================================

export const minimaxShadows = {
  sm: 'rgba(0, 0, 0, 0.3) 0px 2px 4px',
  md: 'rgba(0, 0, 0, 0.3) 0px 4px 6px',
  lg: 'rgba(0, 0, 0, 0.3) 0px 0px 22.576px',
  brand: 'rgba(59, 130, 246, 0.15) 0px 0px 15px', // 品牌蓝色光晕
  xl: 'rgba(0, 0, 0, 0.4) 0px 12px 16px -4px',
}

// ============================================
// 过渡动画
// ============================================

export const minimaxTransitions = {
  fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
  base: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
  slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
}

// ============================================
// 断点系统（用于响应式）
// ============================================

export const minimaxBreakpoints = {
  sm: '640px', // 移动端
  md: '768px', // 平板
  lg: '1024px', // 桌面
  xl: '1280px', // 大桌面
}

// ============================================
// Z-index层级
// ============================================

export const minimaxZIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1100,
  fixed: 1200,
  modalBackdrop: 1300,
  modal: 1400,
  popover: 1500,
  tooltip: 1600,
}

// ============================================
// 工具函数
// ============================================

/**
 * 获取品牌色（带透明度）
 */
export function getBrandColor(opacity: number = 1): string {
  return opacity === 1 ? minimaxColors.brand.primary500 : `rgba(59, 130, 246, ${opacity})`
}

/**
 * 获取语义色
 */
export function getSemanticColor(type: 'rose' | 'emerald' | 'amber' | 'blue'): string {
  return minimaxColors.semantic[type]
}

/**
 * 获取阴影
 */
export function getShadow(type: 'sm' | 'md' | 'lg' | 'brand' | 'xl' = 'md'): string {
  return minimaxShadows[type]
}

/**
 * 获取圆角
 */
export function getRadius(type: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'pill' = 'md'): string {
  return minimaxRadius[type]
}
