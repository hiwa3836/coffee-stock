import { useCallback, useEffect, useRef, useState } from "react";

export function useLongPress(callback: () => void, speed: number = 150) {
  const [isPressing, setIsPressing] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (isPressing) {
      timerRef.current = setInterval(() => callbackRef.current(), speed);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPressing, speed]);

  const start = useCallback(() => {
    callbackRef.current(); 
    setIsPressing(true);
  }, []);

  const stop = useCallback(() => setIsPressing(false), []);

  return {
    onMouseDown: start,
    onMouseUp: stop,
    onMouseLeave: stop,
    onTouchStart: start,
    onTouchEnd: stop,
  };
}
