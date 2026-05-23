import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Avatar from './Avatar';

describe('Avatar', () => {
    it('renders initials', () => {
        render(<Avatar initials="MK" />);
        expect(screen.getByText('MK')).toBeInTheDocument();
    });

    it('truncates initials to 2 characters', () => {
        render(<Avatar initials="ABC" />);
        expect(screen.getByText('AB')).toBeInTheDocument();
    });

    it('renders single character initials', () => {
        render(<Avatar initials="J" />);
        expect(screen.getByText('J')).toBeInTheDocument();
    });

    it('sets title attribute', () => {
        render(<Avatar initials="MK" title="Marek Kowalski" />);
        expect(screen.getByTitle('Marek Kowalski')).toBeInTheDocument();
    });

    it('sets aria-hidden when no title', () => {
        const { container } = render(<Avatar initials="MK" />);
        expect(container.firstChild).toHaveAttribute('aria-hidden', 'true');
    });

    it('does not set aria-hidden when title provided', () => {
        const { container } = render(<Avatar initials="MK" title="User" />);
        expect(container.firstChild).not.toHaveAttribute('aria-hidden');
    });
});
