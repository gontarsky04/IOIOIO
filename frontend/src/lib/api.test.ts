import { describe, it, expect } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { api, toApiError } from './api';

describe('api instance', () => {
    it('has baseURL set to /api', () => {
        expect(api.defaults.baseURL).toBe('/api');
    });

    it('has timeout of 30 seconds', () => {
        expect(api.defaults.timeout).toBe(30_000);
    });
});

describe('toApiError', () => {
    it('extracts status and detail from AxiosError', () => {
        const axiosError = new AxiosError('Request failed', '404', undefined, undefined, {
            status: 404,
            statusText: 'Not Found',
            data: { detail: 'Nie znaleziono' },
            headers: {},
            config: { headers: new AxiosHeaders() },
        });
        const result = toApiError(axiosError);
        expect(result.status).toBe(404);
        expect(result.detail).toBe('Nie znaleziono');
    });

    it('uses error message when no detail in response', () => {
        const axiosError = new AxiosError('Network Error', 'ERR_NETWORK');
        const result = toApiError(axiosError);
        expect(result.status).toBe(0);
        expect(result.detail).toBe('Network Error');
    });

    it('returns fallback for non-Axios errors', () => {
        const result = toApiError(new Error('random error'));
        expect(result.status).toBe(0);
        expect(result.detail).toBe('Wystąpił nieznany błąd');
    });

    it('returns fallback for null/undefined errors', () => {
        expect(toApiError(null)).toEqual({ status: 0, detail: 'Wystąpił nieznany błąd' });
        expect(toApiError(undefined)).toEqual({ status: 0, detail: 'Wystąpił nieznany błąd' });
    });

    it('handles AxiosError with no response', () => {
        const axiosError = new AxiosError('timeout', 'ECONNABORTED');
        const result = toApiError(axiosError);
        expect(result.status).toBe(0);
        expect(result.detail).toBe('timeout');
    });

    it('handles AxiosError with non-string detail', () => {
        const axiosError = new AxiosError('Fail', '422', undefined, undefined, {
            status: 422,
            statusText: 'Unprocessable',
            data: { detail: [{ msg: 'error' }] },
            headers: {},
            config: { headers: new AxiosHeaders() },
        });
        const result = toApiError(axiosError);
        expect(result.status).toBe(422);
        expect(result.detail).toBe('Fail');
    });
});
