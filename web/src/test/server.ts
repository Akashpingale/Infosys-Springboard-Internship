/**
 * The mock API for tests (KIRO_UI_UPGRADE_SPEC.md Section 3.1).
 *
 * Handlers for the feature screens arrive with Prompt E; for now the server exists so the setup
 * file can fail any test that tries to reach a real address.
 */

import { setupServer } from 'msw/node';

export const server = setupServer();
