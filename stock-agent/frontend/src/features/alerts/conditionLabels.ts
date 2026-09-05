import type { AlertConditionType } from '../../types/alerts'

export const CONDITION_LABEL: Record<AlertConditionType, string> = {
  PRICE_ABOVE: 'Price above',
  PRICE_BELOW: 'Price below',
  SCORE_ABOVE: 'Score above',
  SCORE_BELOW: 'Score below',
  DMA_CROSSOVER_GOLDEN: 'Golden cross (50/200-day)',
  DMA_CROSSOVER_DEATH: 'Death cross (50/200-day)',
  REGIME_CHANGE: 'Market regime changes',
}

export const CONDITION_ORDER: AlertConditionType[] = [
  'PRICE_ABOVE', 'PRICE_BELOW', 'SCORE_ABOVE', 'SCORE_BELOW', 'DMA_CROSSOVER_GOLDEN', 'DMA_CROSSOVER_DEATH', 'REGIME_CHANGE',
]
