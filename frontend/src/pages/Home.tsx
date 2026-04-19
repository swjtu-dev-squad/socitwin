import NavigationBar from '@/components/landing/NavigationBar'
import FooterLinks from '@/components/landing/FooterLinks'
import ContentColumn from '@/components/landing/ContentColumn'
import VisualColumn from '@/components/landing/VisualColumn'

export default function Home() {
  return (
    <div className="min-h-screen bg-bg-primary flex flex-col">
      {/* 顶部导航 */}
      <NavigationBar />

      {/* Content Wrapper - 限制宽度，保留呼吸空间 */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-12 xl:px-16 py-12">
        <div className="w-full max-w-7xl">
          {/* 主内容区 - 左右分栏，固定高度 */}
          <main className="flex flex-col lg:flex-row gap-8 lg:gap-12 h-[600px]">
            <ContentColumn className="w-full lg:w-2/5 xl:w-2/5" />
            <VisualColumn className="w-full lg:w-3/5 xl:w-3/5" />
          </main>
        </div>
      </div>

      {/* 底部链接 */}
      <FooterLinks />
    </div>
  )
}
