import { useState, useEffect } from 'react'

/**
 * Debounce a value - returns the value after it stops changing for `delay` ms
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}

/**
 * Throttle a value - returns the value at most once per `interval` ms
 */
export function useThrottle<T>(value: T, interval: number): T {
  const [throttledValue, setThrottledValue] = useState(value)
  const [lastUpdated, setLastUpdated] = useState(Date.now())

  useEffect(() => {
    const now = Date.now()
    if (now - lastUpdated >= interval) {
      setThrottledValue(value)
      setLastUpdated(now)
    } else {
      const timer = setTimeout(() => {
        setThrottledValue(value)
        setLastUpdated(Date.now())
      }, interval - (now - lastUpdated))

      return () => clearTimeout(timer)
    }
  }, [value, interval, lastUpdated])

  return throttledValue
}
