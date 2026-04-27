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

    it('shows suggestion pill with matched keywords and Use button', () => {
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

        expect(screen.getByText(/^suggested:/i)).toBeInTheDocument()
        // 'Diagnostic' appears in both the pill and the card label
        expect(screen.getAllByText('Diagnostic').length).toBeGreaterThanOrEqual(1)
        // Matched keywords visible in the pill
        expect(screen.getByText(/"why did", "caused"/)).toBeInTheDocument()
        // Use button labelled with the suggested mode
        expect(screen.getByText(/use diagnostic/i)).toBeInTheDocument()
        // Dismiss link visible
        expect(screen.getByText(/dismiss/i)).toBeInTheDocument()
    })

    it('Use button calls onSelect with suggested mode', () => {
        const onSelect = vi.fn()
        render(
            <ModeSelector
                {...defaultProps}
                onSelect={onSelect}
                selectedMode="exploratory"
                suggestedMode="segmentation"
            />
        )

        fireEvent.click(screen.getByText(/use segmentation/i))
        expect(onSelect).toHaveBeenCalledWith('segmentation')
    })

    it('Dismiss hides the suggestion pill until the suggestion changes', () => {
        const { rerender } = render(
            <ModeSelector
                {...defaultProps}
                selectedMode="exploratory"
                suggestedMode="forecasting"
                suggestionMatchedKeywords={['forecast']}
            />
        )
        expect(screen.getByText(/use forecasting/i)).toBeInTheDocument()

        fireEvent.click(screen.getByText(/dismiss/i))
        expect(screen.queryByText(/use forecasting/i)).not.toBeInTheDocument()

        // Same suggestion stays dismissed after a re-render.
        rerender(
            <ModeSelector
                {...defaultProps}
                selectedMode="exploratory"
                suggestedMode="forecasting"
                suggestionMatchedKeywords={['forecast']}
            />
        )
        expect(screen.queryByText(/use forecasting/i)).not.toBeInTheDocument()

        // A different suggestion comes back through.
        rerender(
            <ModeSelector
                {...defaultProps}
                selectedMode="exploratory"
                suggestedMode="predictive"
                suggestionMatchedKeywords={['predict']}
            />
        )
        expect(screen.getByText(/use predictive/i)).toBeInTheDocument()
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
