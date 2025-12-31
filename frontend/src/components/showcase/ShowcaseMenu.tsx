/**
 * ShowcaseMenu - Menu for accessing showcase content
 * Split into FGO content and Pan-Human History content
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { ShowcaseContent } from './ShowcaseModal'
import {
  singularities,
  lostbelts,
  servantColumns,
  historyArticles,
  literatureArticles,
  musicArticles
} from '../../data/showcaseData'
import './showcase.css'

interface Props {
  onSelectContent: (content: ShowcaseContent) => void
}

type MainTab = 'fgo' | 'panHuman'
type FgoSubTab = 'singularity' | 'lostbelt' | 'servant'
type PanHumanSubTab = 'history' | 'literature' | 'music'

export function ShowcaseMenu({ onSelectContent }: Props) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const [mainTab, setMainTab] = useState<MainTab>('fgo')
  const [fgoSubTab, setFgoSubTab] = useState<FgoSubTab>('singularity')
  const [panHumanSubTab, setPanHumanSubTab] = useState<PanHumanSubTab>('history')

  const getContentList = (): ShowcaseContent[] => {
    if (mainTab === 'fgo') {
      switch (fgoSubTab) {
        case 'singularity': return singularities
        case 'lostbelt': return lostbelts
        case 'servant': return servantColumns
      }
    } else {
      switch (panHumanSubTab) {
        case 'history': return historyArticles
        case 'literature': return literatureArticles
        case 'music': return musicArticles
      }
    }
  }

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
        <span className="menu-text">{t('showcase.menu.title')}</span>
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
            {getContentList().map((content) => (
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
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
