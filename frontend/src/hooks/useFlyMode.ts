import { useEffect, useCallback, useRef } from 'react'
import { useGlobeStore } from '../store/globeStore'
import type { GlobeMethods } from 'react-globe.gl'

interface UseFlyModeOptions {
  globeRef: React.RefObject<GlobeMethods | undefined>
  enabled: boolean
}

// Convert degrees to radians
const toRad = (deg: number) => (deg * Math.PI) / 180

/**
 * Hook for fly mode camera controls
 * WASD/Arrows: Move forward/backward/left/right
 * Q/E: Turn left/right (yaw)
 * R/F: Ascend/descend (altitude)
 * Shift: Speed boost
 */
export function useFlyMode({ globeRef, enabled }: UseFlyModeOptions) {
  const { cameraPosition, setCameraPosition, flyState, updateFlyState } = useGlobeStore()
  const keysPressed = useRef<Set<string>>(new Set())
  const animationFrame = useRef<number | null>(null)

  // Movement speed (degrees per frame)
  const BASE_SPEED = 0.5
  const TURN_SPEED = 2  // degrees per frame
  const ALT_SPEED = 0.02  // altitude change per frame

  const updatePosition = useCallback(() => {
    if (!enabled || !globeRef.current) return

    const keys = keysPressed.current
    if (keys.size === 0) {
      animationFrame.current = requestAnimationFrame(updatePosition)
      return
    }

    const speedMultiplier = keys.has('Shift') ? 2.5 : 1.0
    const moveSpeed = BASE_SPEED * speedMultiplier * flyState.speed

    let { lat, lng, altitude } = cameraPosition
    let { heading } = flyState

    // Turn left/right (Q/E)
    if (keys.has('q') || keys.has('Q')) {
      heading = (heading - TURN_SPEED * speedMultiplier + 360) % 360
      updateFlyState({ heading })
    }
    if (keys.has('e') || keys.has('E')) {
      heading = (heading + TURN_SPEED * speedMultiplier) % 360
      updateFlyState({ heading })
    }

    // Forward/backward movement (W/S or Up/Down)
    const moveForward = keys.has('w') || keys.has('W') || keys.has('ArrowUp')
    const moveBackward = keys.has('s') || keys.has('S') || keys.has('ArrowDown')

    if (moveForward || moveBackward) {
      const direction = moveForward ? 1 : -1
      const headingRad = toRad(heading)

      // Calculate new position based on heading
      lat += direction * moveSpeed * Math.cos(headingRad)
      lng += direction * moveSpeed * Math.sin(headingRad) / Math.cos(toRad(lat))

      // Clamp latitude
      lat = Math.max(-85, Math.min(85, lat))
      // Wrap longitude
      lng = ((lng + 180) % 360 + 360) % 360 - 180
    }

    // Strafe left/right (A/D or Left/Right)
    const strafeLeft = keys.has('a') || keys.has('A') || keys.has('ArrowLeft')
    const strafeRight = keys.has('d') || keys.has('D') || keys.has('ArrowRight')

    if (strafeLeft || strafeRight) {
      const direction = strafeRight ? 1 : -1
      const strafeHeading = toRad(heading + 90)

      lat += direction * moveSpeed * 0.7 * Math.cos(strafeHeading)
      lng += direction * moveSpeed * 0.7 * Math.sin(strafeHeading) / Math.cos(toRad(lat))

      lat = Math.max(-85, Math.min(85, lat))
      lng = ((lng + 180) % 360 + 360) % 360 - 180
    }

    // Ascend/descend (R/F or Space/Ctrl)
    const ascend = keys.has('r') || keys.has('R') || keys.has(' ')
    const descend = keys.has('f') || keys.has('F') || keys.has('Control')

    if (ascend) {
      altitude = Math.min(4.0, altitude + ALT_SPEED * speedMultiplier)
    }
    if (descend) {
      altitude = Math.max(0.2, altitude - ALT_SPEED * speedMultiplier)
    }

    // Update camera position
    setCameraPosition({ lat, lng, altitude })

    // Apply to globe with smooth transition
    globeRef.current.pointOfView({ lat, lng, altitude }, 50)

    animationFrame.current = requestAnimationFrame(updatePosition)
  }, [enabled, cameraPosition, flyState, setCameraPosition, updateFlyState, globeRef])

  // Key event handlers
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      keysPressed.current.add(e.key)

      // Prevent default for navigation keys
      if (['w', 'a', 's', 'd', 'q', 'e', 'r', 'f', 'W', 'A', 'S', 'D', 'Q', 'E', 'R', 'F',
           'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
        e.preventDefault()
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      keysPressed.current.delete(e.key)
    }

    const handleBlur = () => {
      keysPressed.current.clear()
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('blur', handleBlur)

    // Start animation loop
    animationFrame.current = requestAnimationFrame(updatePosition)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('blur', handleBlur)

      if (animationFrame.current) {
        cancelAnimationFrame(animationFrame.current)
      }
    }
  }, [enabled, updatePosition])

  return {
    heading: flyState.heading,
    speed: flyState.speed,
    setSpeed: (speed: number) => updateFlyState({ speed }),
  }
}
