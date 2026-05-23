import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Modal from './Modal';

describe('Modal', () => {
    it('renders nothing when open is false', () => {
        const { container } = render(
            <Modal open={false} title="Test" onClose={vi.fn()}>
                Content
            </Modal>
        );
        expect(container).toBeEmptyDOMElement();
    });

    it('renders dialog when open is true', () => {
        render(
            <Modal open={true} title="Test Modal" onClose={vi.fn()}>
                Modal content
            </Modal>
        );
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText('Test Modal')).toBeInTheDocument();
        expect(screen.getByText('Modal content')).toBeInTheDocument();
    });

    it('calls onClose when close button is clicked', () => {
        const onClose = vi.fn();
        render(
            <Modal open={true} title="Test" onClose={onClose}>
                Content
            </Modal>
        );
        fireEvent.click(screen.getByLabelText('Zamknij'));
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Escape is pressed', () => {
        const onClose = vi.fn();
        render(
            <Modal open={true} title="Test" onClose={onClose}>
                Content
            </Modal>
        );
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when backdrop is clicked', () => {
        const onClose = vi.fn();
        render(
            <Modal open={true} title="Test" onClose={onClose}>
                Content
            </Modal>
        );
        const backdrop = screen.getByRole('presentation');
        fireEvent.mouseDown(backdrop);
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose when dialog content is clicked', () => {
        const onClose = vi.fn();
        render(
            <Modal open={true} title="Test" onClose={onClose}>
                <button>Inside</button>
            </Modal>
        );
        fireEvent.mouseDown(screen.getByText('Inside'));
        expect(onClose).not.toHaveBeenCalled();
    });

    it('renders footer when provided', () => {
        render(
            <Modal open={true} title="Test" onClose={vi.fn()} footer={<button>Save</button>}>
                Content
            </Modal>
        );
        expect(screen.getByText('Save')).toBeInTheDocument();
    });

    it('sets aria-label on dialog', () => {
        render(
            <Modal open={true} title="My Title" onClose={vi.fn()}>
                Content
            </Modal>
        );
        expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'My Title');
    });
});
