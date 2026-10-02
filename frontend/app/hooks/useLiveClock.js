import { useEffect, useState } from 'react';

export function useLiveClock(interval = 30000) {
  const [currentTime, setCurrentTime] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(new Date()), interval);
    return () => window.clearInterval(timer);
  }, [interval]);

  return currentTime;
}
