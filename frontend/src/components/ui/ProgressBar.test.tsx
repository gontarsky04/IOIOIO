import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ProgressBar from './ProgressBar';

describe('ProgressBar', () => {
    it('renders a progressbar role element', () => {
        render(<ProgressBar value={0.5} />);
        expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('sets correct aria-valuenow', () => {
        render(<ProgressBar value={0.75} />);
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0.75');
    });

    it('clamps value to 0 minimum', () => {
        render(<ProgressBar value={-0.5} />);
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0');
    });

    it('clamps value to 1 maximum', () => {
        render(<ProgressBar value={1.5} />);
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
    });

    it('sets width style based on value', () => {
        render(<ProgressBar value={0.6} />);
        const bar = screen.getByRole('progressbar');
        expect(bar).toHaveStyle({ width: '60%' });
    });

    it('renders labels when provided', () => {
        render(<ProgressBar value={0.5} leftLabel="Start" rightLabel="End" />);
        expect(screen.getByText('Start')).toBeInTheDocument();
        expect(screen.getByText('End')).toBeInTheDocument();
    });

    it('does not render labels container when no labels provided', () => {
        const { container } = render(<ProgressBar value={0.5} />);
        const labelDiv = container.querySelector('[class*="label"]');
        expect(labelDiv).not.toBeInTheDocument();
    });
});
