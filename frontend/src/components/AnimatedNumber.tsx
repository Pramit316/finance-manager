import React, { useEffect, useState } from 'react';

interface AnimatedNumberProps {
  value: number | string | null | undefined;
  format?: (val: number) => string;
  duration?: number;
}

export const AnimatedNumber: React.FC<AnimatedNumberProps> = ({ 
  value, 
  format = (v) => String(v), 
  duration = 1200 
}) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const target = parseFloat(String(value ?? 0).replace(/,/g, ''));
    if (isNaN(target)) {
      setDisplayValue(0);
      return;
    }

    let startTimestamp: number;
    const startValue = 0; // Always animate from 0 on load/update

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      
      // easeOutExpo
      const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      
      setDisplayValue(startValue + (target - startValue) * easeProgress);

      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        setDisplayValue(target);
      }
    };

    window.requestAnimationFrame(step);
  }, [value, duration]);

  return <>{format(displayValue)}</>;
};
