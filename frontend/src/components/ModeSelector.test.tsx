import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ModeSelector, ANALYSIS_MODES } from './ModeSelector'

describe('ModeSelector', () => {
    const defaultProps = {
        selectedMode: 'exploratory' as const,
        onSelect: vi.fn(),
    }

    it('renders all 7 analysis modes', () => {
        render(<ModeSelector {...defaultProps} />)
        for (const mode of ANALYSIS_MODES) {
            expect(screen.getByText(mode.label)).toBeInTheDocument()
        }
    })

    it('calls onSelect when a mode button is clicked', () => {
        const onSelect = vi.fn()
        render(<ModeSelector {...defaultProps} onSelect={onSelect} />)

        fireEvent.click(screen.getByText('Predictive'))
        expect(onSelect).toHaveBeenCalledWith('predictive')
    })

    it('marks the selected mode with aria-checked', () => {
        render(<ModeSelector {...defaultProps} selectedMode="forecasting" />)

        const forecastBtn = screen.getByRole('radio', { name: /forecasting mode/i })
        expect(forecastBtn).toHaveAttribute('aria-checked', 'true')

        const exploratoryBtn = screen.getByRole('radio', { name: /exploratory mode/i })
        expect(exploratoryBtn).toHaveAttribute('aria-checked', 'false')
    })

    it('shows "Suggested" badge when suggestedMode differs from selected', () => {
        render(
            <ModeSelector
                {...defaultProps}
                selectedMode="exploratory"
                suggestedMode="forecasting"
            />
        )

        expect(screen.getByText('Suggested')).toBeInTheDocument()
    })

    it('does not show suggestion badge when suggestedMode matches selected', () => {
        render(
            <ModeSelector
                {...defaultProps}
                selectedMode="forecasting"
                suggestedMode="forecasting"
            />
        )

        expect(screen.queryByText('Suggested')).not.toBeInTheDocument()
    })

    it('shows AI suggestion banner with matched keywords and Apply button', () => {
        render(
            <ModeSelector
                {...defaultProps}
                selectedMode="exploratory"
                suggestedMode="diagnostic"
                suggestionExplanation='matched "why did", "caused"'
                suggestionConfidence={0.7}
                suggestionMatchedKeywords={['why did', 'caused']}
            />
        )

        expect(screen.getByText(/ai suggests/i)).toBeInTheDocument()
        // 'Diagnostic' appears in both the banner and the card label
        expect(screen.getAllByText('Diagnostic').length).toBeGreaterThanOrEqual(1)
        // Matched keywords are visible in the banner
        expect(screen.getByText(/matched "why did", "caused"/)).toBeInTheDocument()
        expect(screen.getByText('Apply')).toBeInTheDocument()
    })

    it('Apply button calls onSelect with suggested mode', () => {
        const onSelect = vi.fn()
        render(
            <ModeSelector
                {...defaultProps}
                onSelect={onSelect}
                selectedMode="exploratory"
                suggestedMode="segmentation"
            />
        )

        fireEvent.click(screen.getByText('Apply'))
        expect(onSelect).toHaveBeenCalledWith('segmentation')
    })

    it('does not show suggestion banner when no suggestedMode', () => {
        render(<ModeSelector {...defaultProps} />)

        expect(screen.queryByText(/ai suggests/i)).not.toBeInTheDocument()
        expect(screen.queryByText('Apply')).not.toBeInTheDocument()
    })

    it('renders info icon for each mode', () => {
        render(<ModeSelector {...defaultProps} />)

        const infoButtons = screen.getAllByLabelText('More info')
        expect(infoButtons.length).toBe(ANALYSIS_MODES.length)
    })

    it('shows tooltip on info icon click', () => {
        render(<ModeSelector {...defaultProps} />)

        const infoButtons = screen.getAllByLabelText('More info')
        fireEvent.click(infoButtons[0])

        // Should now show the detailed description for exploratory
        expect(screen.getByText(/comprehensive data profiling/i)).toBeInTheDocument()
    })

    it('each mode has a detailedDesc in ANALYSIS_MODES', () => {
        for (const mode of ANALYSIS_MODES) {
            expect(mode.detailedDesc).toBeDefined()
            expect(mode.detailedDesc.length).toBeGreaterThan(20)
        }
    })
})
