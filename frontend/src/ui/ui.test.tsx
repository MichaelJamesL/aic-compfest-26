import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { Donut, DonutLegend } from './Donut'
import { StateTrack } from './StateTrack'
import { StatusDot } from './Badge'
import { Bars, ConfidenceBar } from './Bars'

// Vitest globals are off, so Testing Library's auto-cleanup does not run.
afterEach(cleanup)

const segments = [
  { label: 'Sisa skor', value: 48, color: 'var(--color-raised)' },
  { label: 'Anomali', value: 20, color: 'var(--color-crit)' },
  { label: 'Overdue & berulang', value: 32, color: 'var(--color-clay)' },
]

describe('Donut', () => {
  it('draws one arc per non-zero segment', () => {
    const { container } = render(<Donut segments={segments} value={48} suffix="/100" />)
    expect(container.querySelectorAll('circle')).toHaveLength(3)
  })

  it('leaves a gap between segments so they read as separate', () => {
    const { container } = render(<Donut segments={segments} value={48} />)
    const circumference = 2 * Math.PI * ((150 - 26) / 2)
    const first = container.querySelector('circle')!
    const [visible] = first.getAttribute('stroke-dasharray')!.split(' ').map(Number)
    // 48% of the ring, minus the 2px gap.
    expect(visible).toBeCloseTo((48 / 100) * circumference - 2, 1)
  })

  it('shows the value and caption in the centre', () => {
    render(<Donut segments={segments} value={48} suffix="/100" caption="Menurun" />)
    expect(screen.getByText('48')).toBeTruthy()
    expect(screen.getByText('Menurun')).toBeTruthy()
  })

  it('survives an all-zero breakdown without dividing by zero', () => {
    const { container } = render(<Donut segments={[]} value={0} />)
    expect(container.querySelectorAll('circle')).toHaveLength(0)
  })
})

describe('DonutLegend', () => {
  it('labels each segment with its share', () => {
    render(<DonutLegend segments={segments} />)
    expect(screen.getByText('Anomali')).toBeTruthy()
    expect(screen.getByText('20%')).toBeTruthy()
  })
})

describe('StateTrack', () => {
  it('names every step of the happy path', () => {
    render(<StateTrack status="approved" />)
    for (const label of ['Draft', 'Disetujui', 'Dikerjakan', 'Selesai']) {
      expect(screen.getByText(label)).toBeTruthy()
    }
  })

  it('appends the terminal state when a work order is rejected', () => {
    render(<StateTrack status="rejected" />)
    expect(screen.getByText('Ditolak')).toBeTruthy()
  })
})

describe('StatusDot', () => {
  it('always renders a label beside the dot — colour is never the only channel', () => {
    const { container } = render(<StatusDot tone="crit">Kritis</StatusDot>)
    expect(screen.getByText('Kritis')).toBeTruthy()
    expect(container.querySelector('[aria-hidden]')).toBeTruthy()
  })
})

describe('Bars', () => {
  const bars = [
    { label: 'Batch 1', value: 0.12 },
    { label: 'Batch 2', value: 0.31, highlighted: true },
    { label: 'Batch 3', value: 0.08 },
  ]

  it('labels every bar on the axis', () => {
    render(<Bars bars={bars} />)
    for (const bar of bars) expect(screen.getByText(bar.label)).toBeTruthy()
  })

  it('scales bar heights against the largest value, with a visible floor', () => {
    const { container } = render(<Bars bars={bars} />)
    // The first match is the chart's own pixel height; the bars are the
    // percentage ones.
    const heights = [...container.querySelectorAll('[style*="height"]')]
      .map((el) => (el as HTMLElement).style.height)
      .filter((height) => height.endsWith('%'))
    expect(heights).toHaveLength(3)
    expect(heights[1]).toBe('100%') // the largest value fills the chart
    expect(parseFloat(heights[0])).toBeCloseTo((0.12 / 0.31) * 100, 1)
    expect(parseFloat(heights[2])).toBeGreaterThanOrEqual(2) // never invisible
  })

  it('reveals a tooltip with the formatted value on hover, and hides it after', () => {
    const { container } = render(<Bars bars={bars} format={(v) => `${Math.round(v * 100)}%`} />)
    const column = container.querySelectorAll('.relative.flex.flex-1')[1]
    expect(screen.queryByText('31%')).toBeNull()

    fireEvent.mouseEnter(column)
    expect(screen.getByText('31%')).toBeTruthy()
    // The tooltip is the one sanctioned glass element in a chart.
    expect(container.querySelector('.glass-light')).toBeTruthy()

    fireEvent.mouseLeave(column)
    expect(screen.queryByText('31%')).toBeNull()
  })

  it('dims the other bars while one is hovered', () => {
    const { container } = render(<Bars bars={bars} />)
    const columns = container.querySelectorAll('.relative.flex.flex-1')
    fireEvent.mouseEnter(columns[0])
    const opacities = [...container.querySelectorAll('[style*="opacity"]')].map(
      (el) => (el as HTMLElement).style.opacity,
    )
    expect(opacities[0]).toBe('1')
    expect(opacities[1]).toBe('0.6')
  })
})

describe('ConfidenceBar', () => {
  it('renders the confidence as a percentage', () => {
    render(<ConfidenceBar value={0.7} />)
    expect(screen.getByText('70%')).toBeTruthy()
  })

  it('clamps out-of-range values', () => {
    render(<ConfidenceBar value={1.8} />)
    expect(screen.getByText('100%')).toBeTruthy()
  })
})
