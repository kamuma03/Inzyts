import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorBoundary from './ErrorBoundary'

const ThrowingComponent = () => {
    throw new Error('Test error')
}

const SafeComponent = () => <div>Safe content</div>

describe('ErrorBoundary', () => {
    it('renders children when no error', () => {
        render(
            <ErrorBoundary>
                <SafeComponent />
            </ErrorBoundary>
        )
        expect(screen.getByText('Safe content')).toBeInTheDocument()
    })

    it('renders error UI when child throws', () => {
        // Suppress console.error from React's error boundary logging
        const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

        render(
            <ErrorBoundary>
                <ThrowingComponent />
            </ErrorBoundary>
        )

        expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
        expect(screen.getByText(/reload page/i)).toBeInTheDocument()

        spy.mockRestore()
    })

    it('has a reload button that reloads the page', () => {
        const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
        const reloadMock = vi.fn()
        Object.defineProperty(window, 'location', {
            value: { ...window.location, reload: reloadMock },
            writable: true,
        })

        render(
            <ErrorBoundary>
                <ThrowingComponent />
            </ErrorBoundary>
        )

        fireEvent.click(screen.getByText(/reload page/i))
        expect(reloadMock).toHaveBeenCalled()

        spy.mockRestore()
    })
})
