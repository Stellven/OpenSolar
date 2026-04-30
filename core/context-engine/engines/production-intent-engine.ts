import { SmartHandler } from '../../intent/smart-handler';
import { existsSync, readFileSync } from 'fs';
import type { PluginInitContext, RouteHint } from '../types';

export type ProductionIntentResult = {
  intent: string;
  routeHint: RouteHint;
  confidence: number;
  source: 'smart_handler' | 'fallback';
  reason?: string;
};

const VALID_ROUTES: RouteHint[] = ['/review', '/build', '/office', '/research'];
const ROUTE_RULES_PATH = `${process.env.PROJECT_ROOT || '.'}/core/context-engine/route-rules.json`;

type RouteRuleConfig = {
  version: number;
  defaultRoute: RouteHint;
  rules: Array<{ route: RouteHint; keywords: string[] }>;
};

function mapSmartIntentToRoute(intent: string, input: string): RouteHint {
  const text = (input || '').toLowerCase();
  const isHealthCheck = /健康|状态|体检|诊断|health|status|check/.test(text);

  switch (intent) {
    case 'analyze':
    case 'summarize':
    case 'translate':
    case 'search':
    case 'question':
    case 'learn':
      return '/research';
    case 'remind':
      return '/office';
    case 'execute':
      return isHealthCheck ? '/review' : '/build';
    default:
      return '/review';
  }
}

export class ProductionIntentEngine {
  private smartHandler: SmartHandler;
  private logger: PluginInitContext['logger'];
  private routeRules: RouteRuleConfig;

  constructor(logger: PluginInitContext['logger']) {
    this.logger = logger;
    this.smartHandler = new SmartHandler();
    this.routeRules = this.loadRouteRules();
  }

  async infer(input: string): Promise<ProductionIntentResult> {
    try {
      const result = await this.smartHandler.handle(input);
      const explicit = this.normalizeRoute(result.routeHint);
      const learned = !explicit ? this.routeByRules(input) : undefined;
      const routeHint = explicit || learned || mapSmartIntentToRoute(result.intent, input);
      const confidence = explicit
        ? 0.88
        : learned
          ? 0.8
          : result.intent === 'unknown'
            ? 0.45
            : 0.72;

      return {
        intent: result.intent || 'unknown',
        routeHint,
        confidence,
        source: 'smart_handler',
      };
    } catch (error) {
      this.logger.warn('production intent engine fallback route used', { error: String(error) });
      return {
        intent: 'unknown',
        routeHint: '/review',
        confidence: 0.2,
        source: 'fallback',
        reason: String(error),
      };
    }
  }

  close(): void {
    this.smartHandler.close();
  }

  private normalizeRoute(route?: unknown): RouteHint | undefined {
    if (!route || typeof route !== 'string') return undefined;
    return (VALID_ROUTES as string[]).includes(route) ? (route as RouteHint) : undefined;
  }

  private loadRouteRules(): RouteRuleConfig {
    const fallback: RouteRuleConfig = {
      version: 1,
      defaultRoute: '/review',
      rules: [
        { route: '/review', keywords: ['健康', '状态', '诊断', '检查', 'health', 'status', 'check'] },
        { route: '/build', keywords: ['修', '改', '实现', '编译', '报错', 'fix', 'build', 'implement', 'error'] },
        { route: '/office', keywords: ['提醒', '日程', '待办', '会议', 'calendar', 'todo', 'remind'] },
        { route: '/research', keywords: ['调研', '研究', '分析', '总结', 'research', 'analyze', 'summary'] },
      ],
    };

    try {
      if (!existsSync(ROUTE_RULES_PATH)) return fallback;
      const parsed = JSON.parse(readFileSync(ROUTE_RULES_PATH, 'utf8')) as RouteRuleConfig;
      if (!parsed || !Array.isArray(parsed.rules)) return fallback;
      return parsed;
    } catch {
      return fallback;
    }
  }

  private routeByRules(input: string): RouteHint | undefined {
    const text = (input || '').toLowerCase();
    let best: { route: RouteHint; score: number } | null = null;
    for (const rule of this.routeRules.rules || []) {
      const kws = Array.isArray(rule.keywords) ? rule.keywords : [];
      let score = 0;
      for (const kw of kws) {
        if (!kw) continue;
        if (text.includes(String(kw).toLowerCase())) score += 1;
      }
      if (score > 0 && (!best || score > best.score)) {
        best = { route: rule.route, score };
      }
    }
    return best?.route;
  }
}
