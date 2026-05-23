import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Pagination from './Pagination';

describe('Pagination', () => {
    const defaultProps = {
        page: 2,
        pageCount: 5,
        total: 50,
        pageSize: 10,
        itemsShown: 10,
        onPageChange: vi.fn(),
    };

    it('displays correct range text', () => {
        render(<Pagination {...defaultProps} />);
        expect(screen.getByText(/Pokazano 11–20 z 50 wpisów/)).toBeInTheDocument();
    });

    it('displays correct page indicator', () => {
        render(<Pagination {...defaultProps} />);
        expect(screen.getByText('2 / 5')).toBeInTheDocument();
    });

    it('displays "Brak wpisów" when total is 0', () => {
        render(<Pagination {...defaultProps} total={0} page={1} pageCount={0} itemsShown={0} />);
        expect(screen.getByText('Brak wpisów')).toBeInTheDocument();
    });

    it('uses custom label', () => {
        render(<Pagination {...defaultProps} label="firm" />);
        expect(screen.getByText(/Pokazano 11–20 z 50 firm/)).toBeInTheDocument();
    });

    it('disables prev button on first page', () => {
        render(<Pagination {...defaultProps} page={1} />);
        expect(screen.getByLabelText('Poprzednia strona')).toBeDisabled();
    });

    it('disables next button on last page', () => {
        render(<Pagination {...defaultProps} page={5} />);
        expect(screen.getByLabelText('Następna strona')).toBeDisabled();
    });

    it('enables both buttons on middle page', () => {
        render(<Pagination {...defaultProps} page={3} />);
        expect(screen.getByLabelText('Poprzednia strona')).not.toBeDisabled();
        expect(screen.getByLabelText('Następna strona')).not.toBeDisabled();
    });

    it('calls onPageChange with previous page', () => {
        const onPageChange = vi.fn();
        render(<Pagination {...defaultProps} onPageChange={onPageChange} />);
        fireEvent.click(screen.getByLabelText('Poprzednia strona'));
        expect(onPageChange).toHaveBeenCalledWith(1);
    });

    it('calls onPageChange with next page', () => {
        const onPageChange = vi.fn();
        render(<Pagination {...defaultProps} onPageChange={onPageChange} />);
        fireEvent.click(screen.getByLabelText('Następna strona'));
        expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it('shows dash when pageCount is 0', () => {
        render(<Pagination {...defaultProps} pageCount={0} total={0} page={1} itemsShown={0} />);
        expect(screen.getByText('—')).toBeInTheDocument();
    });
});
