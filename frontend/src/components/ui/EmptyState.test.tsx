import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import EmptyState from './EmptyState';

describe('EmptyState', () => {
    it('renders children', () => {
        render(<EmptyState>No data available</EmptyState>);
        expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('renders title when provided', () => {
        render(<EmptyState title="Empty">Nothing here</EmptyState>);
        expect(screen.getByText('Empty')).toBeInTheDocument();
        expect(screen.getByText('Nothing here')).toBeInTheDocument();
    });

    it('does not render title when not provided', () => {
        const { container } = render(<EmptyState>Content only</EmptyState>);
        const titleElements = container.querySelectorAll('[class*="title"]');
        expect(titleElements.length).toBe(0);
    });
});
