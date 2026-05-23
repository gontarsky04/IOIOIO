import { describe, it, expect } from 'vitest';
import { ROLE_PROFILES, ROLES, roleLabel, type UserRole } from './auth';

describe('auth context exports', () => {
    it('ROLES contains exactly three roles', () => {
        expect(ROLES).toHaveLength(3);
        expect(ROLES).toContain('koordynator');
        expect(ROLES).toContain('opiekun');
        expect(ROLES).toContain('promocja');
    });

    it('ROLE_PROFILES has entries for all roles', () => {
        for (const role of ROLES) {
            expect(ROLE_PROFILES[role]).toBeDefined();
            expect(ROLE_PROFILES[role].label).toBeTruthy();
        }
    });

    it('roleLabel returns correct label for koordynator', () => {
        expect(roleLabel('koordynator')).toBe('Koordynator wydarzenia');
    });

    it('roleLabel returns correct label for opiekun', () => {
        expect(roleLabel('opiekun')).toBe('Opiekun partnerów');
    });

    it('roleLabel returns correct label for promocja', () => {
        expect(roleLabel('promocja')).toBe('Dział promocji');
    });

    it('does not contain zarzad or merytoryczna roles', () => {
        const roleNames = Object.keys(ROLE_PROFILES);
        expect(roleNames).not.toContain('zarzad');
        expect(roleNames).not.toContain('merytoryczna');
    });
});
