import { useState, useEffect } from 'react'

interface TypewriterTextProps {
  text: string
  speed?: number
  className?: string
}

export default function TypewriterText({ text, speed = 80, className = '' }: TypewriterTextProps) {
  const [displayText, setDisplayText] = useState('')
  const [isComplete, setIsComplete] = useState(false)

  useEffect(() => {
    let index = 0
    let timer: number

    const startTyping = () => {
      timer = window.setInterval(() => {
        if (index < text.length) {
          setDisplayText(text.slice(0, index + 1))
          index++
        } else {
          setIsComplete(true)
          clearInterval(timer)
        }
      }, speed)
    }

    // 延迟 300ms 开始打字
    const delayTimer = setTimeout(startTyping, 300)

    return () => {
      clearTimeout(delayTimer)
      clearInterval(timer)
    }
  }, [text, speed])

  return (
    <div className={className}>
      <span className="text-2xl text-accent font-black font-sans">{displayText}</span>
      {!isComplete && (
        <span className="inline-block w-0.5 h-6 bg-accent ml-1 animate-pulse align-middle"></span>
      )}
    </div>
  )
}
