import { describe, it, expect } from 'vitest';
import { getErrorMessage } from './errorMessage';

describe('getErrorMessage', () => {
    it('prefers a FastAPI response.data.detail string', () => {
        const err = {
            response: { data: { detail: 'Database URI scheme not allowed' } },
            message: 'Request failed with status code 422',
        };
        expect(getErrorMessage(err)).toBe('Database URI scheme not allowed');
    });

    it('falls back to an axios/Error message when no detail', () => {
        const err = new Error('Network Error');
        expect(getErrorMessage(err)).toBe('Network Error');
    });

    it('falls back to message when detail is not a string', () => {
        const err = {
            response: { data: { detail: [{ loc: ['body'], msg: 'field required' }] } },
            message: 'Request failed with status code 422',
        };
        expect(getErrorMessage(err)).toBe('Request failed with status code 422');
    });

    it('returns a raw string as-is', () => {
        expect(getErrorMessage('plain string error')).toBe('plain string error');
    });

    it('ignores a blank/whitespace detail and uses message', () => {
        const err = { response: { data: { detail: '   ' } }, message: 'boom' };
        expect(getErrorMessage(err)).toBe('boom');
    });

    it('uses the supplied fallback when nothing usable is present', () => {
        expect(getErrorMessage({}, 'Something went wrong')).toBe('Something went wrong');
        expect(getErrorMessage(null, 'Something went wrong')).toBe('Something went wrong');
        expect(getErrorMessage(undefined)).toBe('An error occurred');
    });

    it('ignores a blank message and uses the fallback', () => {
        const err = { message: '   ' };
        expect(getErrorMessage(err, 'fallback here')).toBe('fallback here');
    });
});
