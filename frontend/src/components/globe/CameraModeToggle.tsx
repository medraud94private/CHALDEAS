import { useGlobeStore, type CameraMode } from '../../store/globeStore'

interface CameraModeToggleProps {
  className?: string
}

const MODE_INFO: Record<CameraMode, { icon: string; label: string; hint: string }> = {
  orbit: {
    icon: '🌍',
    label: 'Orbit',
    hint: 'Drag to rotate around globe',
  },
  fly: {
    icon: '✈️',
    label: 'Fly',
    hint: 'WASD to move, Q/E to turn, R/F altitude',
  },
}

export function CameraModeToggle({ className = '' }: CameraModeToggleProps) {
  const { cameraMode, setCameraMode, flyState } = useGlobeStore()

  const toggleMode = () => {
    const nextMode: CameraMode = cameraMode === 'orbit' ? 'fly' : 'orbit'
    setCameraMode(nextMode)
  }

  const currentMode = MODE_INFO[cameraMode]

  return (
    <div className={`camera-mode-toggle ${className}`}>
      <button
        onClick={toggleMode}
        className="mode-button"
        title={currentMode.hint}
      >
        <span className="mode-icon">{currentMode.icon}</span>
        <span className="mode-label">{currentMode.label}</span>
      </button>

      {cameraMode === 'fly' && (
        <div className="fly-info">
          <div className="heading-indicator">
            <span className="compass">🧭</span>
            <span className="heading-value">{Math.round(flyState.heading)}°</span>
          </div>
          <div className="controls-hint">
            WASD: Move | Q/E: Turn | R/F: Alt
          </div>
        </div>
      )}

      <style>{`
        .camera-mode-toggle {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .mode-button {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 12px;
          background: rgba(10, 14, 23, 0.9);
          border: 1px solid rgba(0, 212, 255, 0.3);
          border-radius: 6px;
          color: #00d4ff;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .mode-button:hover {
          background: rgba(0, 212, 255, 0.15);
          border-color: rgba(0, 212, 255, 0.5);
        }

        .mode-icon {
          font-size: 16px;
        }

        .mode-label {
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .fly-info {
          background: rgba(10, 14, 23, 0.85);
          border: 1px solid rgba(251, 191, 36, 0.3);
          border-radius: 4px;
          padding: 6px 10px;
          font-size: 10px;
          color: #8ba4b4;
        }

        .heading-indicator {
          display: flex;
          align-items: center;
          gap: 4px;
          margin-bottom: 4px;
        }

        .compass {
          font-size: 12px;
        }

        .heading-value {
          color: #fbbf24;
          font-weight: 600;
          font-family: monospace;
        }

        .controls-hint {
          color: #64748b;
          font-size: 9px;
        }
      `}</style>
    </div>
  )
}
