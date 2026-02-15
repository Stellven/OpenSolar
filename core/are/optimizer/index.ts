/**
 * ARE Optimizer Module
 *
 * JIT/AOT compilation and hotspot detection
 */

export * from './compiler';
export * from './hotspot';

import { planCompiler } from './compiler';
import { hotspotDetector } from './hotspot';

export default {
  compiler: planCompiler,
  hotspot: hotspotDetector,
};
