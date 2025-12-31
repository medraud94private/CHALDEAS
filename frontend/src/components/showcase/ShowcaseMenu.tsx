/**
 * ShowcaseMenu - Menu for accessing showcase content
 * Split into FGO content and Pan-Human History content
 * Now fetches from backend API with i18n support
 */
import { useState, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import type { ShowcaseContent } from './ShowcaseModal'
import { showcaseApi } from '../../api/client'
import './showcase.css'

interface Props {
  onSelectContent: (content: ShowcaseContent) => void
}

type MainTab = 'fgo' | 'panHuman'
type FgoSubTab = 'singularity' | 'lostbelt' | 'servant'
type PanHumanSubTab = 'history' | 'literature' | 'music'

// Helper to get localized field
function getLocalizedField(item: Record<string, unknown>, field: string, lang: string): string {
  // Try language-specific field first (e.g., title_ko, title_ja)
  const langField = `${field}_${lang}`
  if (lang !== 'en' && item[langField]) {
    return item[langField] as string
  }
  // Fall back to base field
  return (item[field] as string) || ''
}

// Transform API response to ShowcaseContent format with i18n
function transformApiItem(item: Record<string, unknown>, lang: string): ShowcaseContent {
  // Transform sections with localization
  const rawSections = (item.sections as Array<Record<string, unknown>>) || []
  const sections = rawSections.map(s => ({
    title: getLocalizedField(s, 'title', lang) || (s.title as string),
    content: getLocalizedField(s, 'content', lang) || (s.content as string)
  }))

  return {
    id: item.id as string,
    type: item.type as ShowcaseContent['type'],
    title: getLocalizedField(item, 'title', lang),
    subtitle: getLocalizedField(item, 'subtitle', lang) || undefined,
    chapter: item.chapter as string | undefined,
    era: item.era as string | undefined,
    year: item.year as number | undefined,
    location: item.location as string | undefined,
    description: getLocalizedField(item, 'description', lang),
    sections,
    historicalBasis: getLocalizedField(item, 'historical_basis', lang) || undefined,
    relatedServants: ((item.related_servants as Array<Record<string, unknown>>) || []).map(s => ({
      name: s.name as string,
      class: s.class_ as string,
      rarity: s.rarity as number
    })),
    relatedEvents: ((item.related_event_ids as number[]) || []).map(id => ({
      id,
      title: `Event ${id}`,
      year: 0
    })),
    sources: (item.sources as string[]) || []
  }
}

export function ShowcaseMenu({ onSelectContent }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [isOpen, setIsOpen] = useState(false)
  const [mainTab, setMainTab] = useState<MainTab>('fgo')
  const [fgoSubTab, setFgoSubTab] = useState<FgoSubTab>('singularity')
  const [panHumanSubTab, setPanHumanSubTab] = useState<PanHumanSubTab>('history')

  // Fetch all showcase data (include lang in queryKey for refetch on language change)
  const { data: singularitiesData } = useQuery({
    queryKey: ['showcases', 'singularities', lang],
    queryFn: () => showcaseApi.getSingularities(),
    select: (res) => res.data.items.map((item: Record<string, unknown>) => transformApiItem(item, lang)),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  const { data: lostbeltsData } = useQuery({
    queryKey: ['showcases', 'lostbelts', lang],
    queryFn: () => showcaseApi.getLostbelts(),
    select: (res) => res.data.items.map((item: Record<string, unknown>) => transformApiItem(item, lang)),
    staleTime: 5 * 60 * 1000,
  })

  const { data: servantsData } = useQuery({
    queryKey: ['showcases', 'servants', lang],
    queryFn: () => showcaseApi.getServants(),
    select: (res) => res.data.items.map((item: Record<string, unknown>) => transformApiItem(item, lang)),
    staleTime: 5 * 60 * 1000,
  })

  const { data: historyData } = useQuery({
    queryKey: ['showcases', 'history', lang],
    queryFn: () => showcaseApi.getHistory(),
    select: (res) => res.data.items.map((item: Record<string, unknown>) => transformApiItem(item, lang)),
    staleTime: 5 * 60 * 1000,
  })

  const { data: literatureData } = useQuery({
    queryKey: ['showcases', 'literature', lang],
    queryFn: () => showcaseApi.getLiterature(),
    select: (res) => res.data.items.map((item: Record<string, unknown>) => transformApiItem(item, lang)),
    staleTime: 5 * 60 * 1000,
  })

  const { data: musicData } = useQuery({
    queryKey: ['showcases', 'music', lang],
    queryFn: () => showcaseApi.getMusic(),
    select: (res) => res.data.items.map((item: Record<string, unknown>) => transformApiItem(item, lang)),
    staleTime: 5 * 60 * 1000,
  })

  const getContentList = useMemo((): ShowcaseContent[] => {
    if (mainTab === 'fgo') {
      switch (fgoSubTab) {
        case 'singularity': return singularitiesData || []
        case 'lostbelt': return lostbeltsData || []
        case 'servant': return servantsData || []
      }
    } else {
      switch (panHumanSubTab) {
        case 'history': return historyData || []
        case 'literature': return literatureData || []
        case 'music': return musicData || []
      }
    }
  }, [mainTab, fgoSubTab, panHumanSubTab, singularitiesData, lostbeltsData, servantsData, historyData, literatureData, musicData])

  const handleSelect = (content: ShowcaseContent) => {
    onSelectContent(content)
    setIsOpen(false)
  }

  return (
    <div className="showcase-menu-container">
      <button
        className={`showcase-menu-btn ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="menu-icon">◈</span>
        <span className="menu-text-group">
          <span className="menu-title">{t('showcase.menu.title')}</span>
          <span className="menu-subtitle">{t('showcase.menu.subtitle')}</span>
        </span>
      </button>

      {isOpen && (
        <div className="showcase-menu-dropdown">
          {/* Main Tabs: FGO vs Pan-Human History */}
          <div className="showcase-main-tabs">
            <button
              className={`main-tab ${mainTab === 'fgo' ? 'active' : ''}`}
              onClick={() => setMainTab('fgo')}
            >
              <span className="main-tab-icon">◎</span>
              {t('showcase.tabs.fgo')}
            </button>
            <button
              className={`main-tab ${mainTab === 'panHuman' ? 'active' : ''}`}
              onClick={() => setMainTab('panHuman')}
            >
              <span className="main-tab-icon">◉</span>
              {t('showcase.tabs.panHuman')}
            </button>
          </div>

          {/* Sub Tabs */}
          <div className="showcase-menu-tabs">
            {mainTab === 'fgo' ? (
              <>
                <button
                  className={`menu-tab ${fgoSubTab === 'singularity' ? 'active' : ''}`}
                  onClick={() => setFgoSubTab('singularity')}
                >
                  <span className="tab-icon" style={{ color: 'var(--chaldea-orange)' }}>▸</span>
                  {t('showcase.menu.singularities')}
                </button>
                <button
                  className={`menu-tab ${fgoSubTab === 'lostbelt' ? 'active' : ''}`}
                  onClick={() => setFgoSubTab('lostbelt')}
                >
                  <span className="tab-icon" style={{ color: 'var(--chaldea-magenta)' }}>▸</span>
                  {t('showcase.menu.lostbelts')}
                </button>
                <button
                  className={`menu-tab ${fgoSubTab === 'servant' ? 'active' : ''}`}
                  onClick={() => setFgoSubTab('servant')}
                >
                  <span className="tab-icon" style={{ color: 'var(--chaldea-gold)' }}>▸</span>
                  {t('showcase.menu.servants')}
                </button>
              </>
            ) : (
              <>
                <button
                  className={`menu-tab ${panHumanSubTab === 'history' ? 'active' : ''}`}
                  onClick={() => setPanHumanSubTab('history')}
                >
                  <span className="tab-icon" style={{ color: 'var(--chaldea-cyan)' }}>▸</span>
                  {t('showcase.menu.history')}
                </button>
                <button
                  className={`menu-tab ${panHumanSubTab === 'literature' ? 'active' : ''}`}
                  onClick={() => setPanHumanSubTab('literature')}
                >
                  <span className="tab-icon" style={{ color: 'var(--chaldea-green)' }}>▸</span>
                  {t('showcase.menu.literature')}
                </button>
                <button
                  className={`menu-tab ${panHumanSubTab === 'music' ? 'active' : ''}`}
                  onClick={() => setPanHumanSubTab('music')}
                >
                  <span className="tab-icon" style={{ color: '#9966ff' }}>▸</span>
                  {t('showcase.menu.music')}
                </button>
              </>
            )}
          </div>

          {/* Content List */}
          <div className="showcase-menu-list">
            {getContentList.length === 0 ? (
              <div className="showcase-loading">
                <span className="loading-text">{t('showcase.loading', 'Loading...')}</span>
              </div>
            ) : (
              getContentList.map((content) => (
                <button
                  key={content.id}
                  className="showcase-menu-item"
                  onClick={() => handleSelect(content)}
                >
                  <div className="item-header">
                    {content.chapter && (
                      <span className="item-chapter">{content.chapter}</span>
                    )}
                    <span className="item-title">{content.title}</span>
                  </div>
                  {content.subtitle && (
                    <div className="item-subtitle">{content.subtitle}</div>
                  )}
                  <div className="item-meta">
                    {content.year && (
                      <span>
                        {content.year < 0 ? `${Math.abs(content.year)} BC` : `${content.year} AD`}
                      </span>
                    )}
                    {content.location && <span>{content.location}</span>}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
