/**
 * ARE Monitor Module
 *
 * Dashboard and health checking
 */

export * from './dashboard';
export * from './health';

import { dashboard } from './dashboard';
import { healthChecker } from './health';

export default {
  dashboard,
  health: healthChecker,
};
