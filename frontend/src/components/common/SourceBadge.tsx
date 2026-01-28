/**
 * SourceBadge - Displays source attribution for entity descriptions
 *
 * Shows appropriate icon/badge based on source type:
 * - Wikipedia: Wikipedia logo with language indicator + link
 * - LLM: AI-generated content indicator
 * - Manual: No badge (assumed original content)
 */
import { parseSourceInfo, type SourceInfo } from '../../store/settingsStore'
import './SourceBadge.css'

interface Props {
  source: string | null | undefined
  sourceUrl: string | null | undefined
  compact?: boolean
}

// Language display names
const LANG_NAMES: Record<string, string> = {
  en: 'EN',
  ko: 'KO',
  ja: 'JA',
}

export function SourceBadge({ source, sourceUrl, compact = false }: Props) {
  const info: SourceInfo = parseSourceInfo(source, sourceUrl)

  if (info.type === 'unknown' || info.type === 'manual') {
    return null
  }

  if (info.type === 'wikipedia') {
    const langLabel = info.language ? LANG_NAMES[info.language] || info.language.toUpperCase() : ''

    if (compact) {
      return (
        <span className="source-badge compact wikipedia" title={`Source: Wikipedia (${langLabel})`}>
          <img
            src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/24px-Wikipedia-logo-v2.svg.png"
            alt="Wikipedia"
            className="source-icon"
          />
        </span>
      )
    }

    return (
      <div className="source-badge wikipedia">
        <img
          src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/24px-Wikipedia-logo-v2.svg.png"
          alt="Wikipedia"
          className="source-icon"
        />
        <span className="source-text">
          Wikipedia
          {langLabel && <span className="source-lang">{langLabel}</span>}
        </span>
        {info.url && (
          <a
            href={info.url}
            target="_blank"
            rel="noopener noreferrer"
            className="source-link"
            title="View source article"
          >
            ↗
          </a>
        )}
      </div>
    )
  }

  if (info.type === 'llm') {
    if (compact) {
      return (
        <span className="source-badge compact llm" title="AI-generated content">
          <span className="source-icon ai">✨</span>
        </span>
      )
    }

    return (
      <div className="source-badge llm">
        <span className="source-icon ai">✨</span>
        <span className="source-text">AI Generated</span>
      </div>
    )
  }

  return null
}

/**
 * SourceAttribution - Full attribution block with CC license info
 */
interface AttributionProps {
  source: string | null | undefined
  sourceUrl: string | null | undefined
}

export function SourceAttribution({ source, sourceUrl }: AttributionProps) {
  const info = parseSourceInfo(source, sourceUrl)

  if (info.type !== 'wikipedia') {
    return <SourceBadge source={source} sourceUrl={sourceUrl} />
  }

  return (
    <div className="source-attribution">
      <SourceBadge source={source} sourceUrl={sourceUrl} />
      <span className="attribution-license">
        Content licensed under{' '}
        <a
          href="https://creativecommons.org/licenses/by-sa/4.0/"
          target="_blank"
          rel="noopener noreferrer"
        >
          CC BY-SA 4.0
        </a>
      </span>
    </div>
  )
}
