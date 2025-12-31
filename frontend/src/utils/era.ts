/**
 * Era/Time Period Utilities for CHALDEAS
 */

export interface Era {
  name: string
  nameKo: string
  color: string
  yearRange: string
}

// Define historical eras - Universal World History Periodization
const ERAS: Array<{
  from: number
  to: number
  era: Era
}> = [
  // 선사시대
  {
    from: -100000, to: -3000,
    era: { name: 'PREHISTORY', nameKo: '선사시대', color: '#5a4a3a', yearRange: '~3000 BCE' }
  },
  // 고대 (Ancient)
  {
    from: -3000, to: -500,
    era: { name: 'ANCIENT', nameKo: '고대', color: '#cd7f32', yearRange: '3000-500 BCE' }
  },
  // 고전기 (Classical Antiquity)
  {
    from: -500, to: 500,
    era: { name: 'CLASSICAL', nameKo: '고전고대', color: '#00d4ff', yearRange: '500 BCE - 500 CE' }
  },
  // 중세 (Medieval / Middle Ages)
  {
    from: 500, to: 1500,
    era: { name: 'MEDIEVAL', nameKo: '중세', color: '#8b4513', yearRange: '500-1500 CE' }
  },
  // 근세 (Early Modern)
  {
    from: 1500, to: 1800,
    era: { name: 'EARLY MODERN', nameKo: '근세', color: '#ffd700', yearRange: '1500-1800 CE' }
  },
  // 근대 (Modern)
  {
    from: 1800, to: 1945,
    era: { name: 'MODERN', nameKo: '근대', color: '#708090', yearRange: '1800-1945 CE' }
  },
  // 현대 (Contemporary)
  {
    from: 1945, to: 2100,
    era: { name: 'CONTEMPORARY', nameKo: '현대', color: '#00ff88', yearRange: '1945-Present' }
  },
]

// Default era for very ancient times
const PREHISTORIC: Era = {
  name: 'PREHISTORY',
  nameKo: '선사시대',
  color: '#5a4a3a',
  yearRange: 'Before History'
}

/**
 * Get the era information for a given year
 */
export function getEra(year: number): Era {
  for (const { from, to, era } of ERAS) {
    if (year >= from && year < to) {
      return era
    }
  }

  // Before Bronze Age
  if (year < -3500) {
    return PREHISTORIC
  }

  // Default for unknown
  return {
    name: 'UNKNOWN ERA',
    nameKo: '미확인',
    color: '#666666',
    yearRange: 'Unknown'
  }
}

/**
 * Format year with era label
 */
export function formatYearWithEra(year: number): {
  year: number
  era: string
  eraName: string
  eraNameKo: string
  eraColor: string
} {
  const absYear = Math.abs(year)
  const eraLabel = year < 0 ? 'BCE' : 'CE'
  const eraInfo = getEra(year)

  return {
    year: absYear,
    era: eraLabel,
    eraName: eraInfo.name,
    eraNameKo: eraInfo.nameKo,
    eraColor: eraInfo.color
  }
}

/**
 * Get a brief context for the era
 */
export function getEraContext(year: number): string {
  const era = getEra(year)

  const contexts: Record<string, string> = {
    'PREHISTORY': '문자 기록 이전, 수렵채집과 농경의 시작',
    'ANCIENT': '문명의 탄생, 이집트·메소포타미아·중국·인도',
    'CLASSICAL': '그리스·로마, 페르시아, 춘추전국, 마우리아 제국',
    'MEDIEVAL': '봉건제, 비잔틴, 이슬람 황금기, 당·송',
    'EARLY MODERN': '대항해시대, 르네상스, 종교개혁, 절대왕정',
    'MODERN': '산업혁명, 제국주의, 세계대전',
    'CONTEMPORARY': '냉전, 디지털 혁명, 세계화',
  }

  return contexts[era.name] || '관측 중인 시대'
}
