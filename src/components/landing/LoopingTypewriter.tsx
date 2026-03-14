import { useState, useEffect } from 'react';

interface LoopingTypewriterProps {
  texts: string[];
  speed?: number;
  deleteSpeed?: number;
  pauseDuration?: number;
  className?: string;
}

export default function LoopingTypewriter({
  texts,
  speed = 100,
  deleteSpeed = 50,
  pauseDuration = 2000,
  className = '',
}: LoopingTypewriterProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [displayText, setDisplayText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    const currentText = texts[currentIndex];

    const timer = setTimeout(() => {
      if (isPaused) {
        return;
      }

      if (isDeleting) {
        if (displayText.length > 0) {
          setDisplayText(displayText.slice(0, -1));
        } else {
          setIsDeleting(false);
          setCurrentIndex((prev) => (prev + 1) % texts.length);
        }
      } else {
        if (displayText.length < currentText.length) {
          setDisplayText(currentText.slice(0, displayText.length + 1));
        } else {
          // 完成输入，暂停一下
          setIsPaused(true);
          setTimeout(() => {
            setIsPaused(false);
            setIsDeleting(true);
          }, pauseDuration);
        }
      }
    }, isDeleting ? deleteSpeed : speed);

    return () => clearTimeout(timer);
  }, [displayText, isDeleting, isPaused, currentIndex, texts, speed, deleteSpeed, pauseDuration]);

  return (
    <div className={className}>
      <span className="text-xl lg:text-2xl text-white font-black font-sans">
        {displayText}
      </span>
      <span className="inline-block w-0.5 h-6 bg-white ml-1 animate-pulse align-middle"></span>
    </div>
  );
}
