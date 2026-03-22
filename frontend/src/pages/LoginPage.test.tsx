import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from './LoginPage'

// Mock react-router-dom navigation
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom')
    return {
        ...actual,
        useNavigate: () => mockNavigate,
        useLocation: () => ({ state: null, pathname: '/login' }),
    }
})

// Mock the API
vi.mock('../api', () => ({
    AnalysisAPI: {
        login: vi.fn(),
    },
}))

import { AnalysisAPI } from '../api'

describe('LoginPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        sessionStorage.clear()
    })

    const renderLogin = () =>
        render(
            <MemoryRouter>
                <LoginPage />
            </MemoryRouter>
        )

    it('renders login form with username and password fields', () => {
        renderLogin()
        expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    })

    it('renders branding elements', () => {
        renderLogin()
        expect(screen.getByText('Inzyts')).toBeInTheDocument()
        expect(screen.getByText(/analyze.*predict.*discover/i)).toBeInTheDocument()
    })

    it('handles successful login', async () => {
        const user = userEvent.setup()
        vi.mocked(AnalysisAPI.login).mockResolvedValueOnce({
            access_token: 'test_jwt_token',
            token_type: 'bearer',
        })

        renderLogin()

        await user.type(screen.getByLabelText(/username/i), 'admin')
        await user.type(screen.getByLabelText(/password/i), 'password')
        await user.click(screen.getByRole('button', { name: /sign in/i }))

        await waitFor(() => {
            expect(sessionStorage.getItem('inzyts_jwt_token')).toBe('test_jwt_token')
            expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
        })
    })

    it('displays error on failed login', async () => {
        const user = userEvent.setup()
        vi.mocked(AnalysisAPI.login).mockRejectedValueOnce({
            response: { data: { detail: 'Incorrect username or password' } },
        })

        renderLogin()

        await user.type(screen.getByLabelText(/username/i), 'admin')
        await user.type(screen.getByLabelText(/password/i), 'wrong')
        await user.click(screen.getByRole('button', { name: /sign in/i }))

        await waitFor(() => {
            expect(screen.getByText('Incorrect username or password')).toBeInTheDocument()
        })
    })

    it('displays generic error when no detail provided', async () => {
        const user = userEvent.setup()
        vi.mocked(AnalysisAPI.login).mockRejectedValueOnce(new Error('Network error'))

        renderLogin()

        await user.type(screen.getByLabelText(/username/i), 'admin')
        await user.type(screen.getByLabelText(/password/i), 'pass')
        await user.click(screen.getByRole('button', { name: /sign in/i }))

        await waitFor(() => {
            expect(screen.getByText(/login failed/i)).toBeInTheDocument()
        })
    })

    it('disables button while loading', async () => {
        const user = userEvent.setup()
        // Create a promise that won't resolve immediately
        let resolveLogin: (value: any) => void
        vi.mocked(AnalysisAPI.login).mockReturnValueOnce(
            new Promise((resolve) => { resolveLogin = resolve })
        )

        renderLogin()

        await user.type(screen.getByLabelText(/username/i), 'admin')
        await user.type(screen.getByLabelText(/password/i), 'pass')
        await user.click(screen.getByRole('button', { name: /sign in/i }))

        // Button should be disabled while loading
        expect(screen.getByRole('button')).toBeDisabled()

        // Resolve the promise
        resolveLogin!({ access_token: 'tok', token_type: 'bearer' })
    })

    it('redirects if token already exists', () => {
        sessionStorage.setItem('inzyts_jwt_token', 'existing_token')
        renderLogin()
        expect(mockNavigate).toHaveBeenCalledWith('/')
    })
})
