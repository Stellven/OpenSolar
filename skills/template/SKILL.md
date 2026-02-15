# /template - 代码模板生成

## 触发
- `/template list` - 列出可用模板
- `/template <类型> <名称>` - 生成代码
- `/template component <名称>` - React 组件
- `/template api <名称>` - API 端点
- `/template test <名称>` - 测试文件
- `/template hook <名称>` - React Hook

## 执行

### 列出模板

```bash
echo "=== 可用模板 ==="
echo "component  - React 组件 (TSX)"
echo "api        - API 端点 (Express/Next)"
echo "test       - 测试文件 (Jest/Vitest)"
echo "hook       - React Hook"
echo "service    - 服务类"
echo "model      - 数据模型"
echo "cli        - CLI 命令"
echo "skill      - Solar Skill"
```

### React 组件模板

```typescript
// templates/component.tsx
import React from 'react';

interface ${NAME}Props {
  // props
}

export const ${NAME}: React.FC<${NAME}Props> = (props) => {
  return (
    <div className="${name}">
      {/* content */}
    </div>
  );
};

export default ${NAME};
```

### API 端点模板

```typescript
// templates/api.ts
import { Request, Response } from 'express';

export async function ${name}Handler(req: Request, res: Response) {
  try {
    // TODO: implement
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' });
  }
}
```

### 测试模板

```typescript
// templates/test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { ${NAME} } from './${name}';

describe('${NAME}', () => {
  beforeEach(() => {
    // setup
  });

  it('should work correctly', () => {
    // TODO: implement test
    expect(true).toBe(true);
  });

  it('should handle edge cases', () => {
    // TODO: implement test
  });
});
```

### React Hook 模板

```typescript
// templates/hook.ts
import { useState, useEffect, useCallback } from 'react';

export function use${NAME}(initialValue?: any) {
  const [state, setState] = useState(initialValue);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // TODO: implement
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  return { state, loading, error, execute };
}
```

### 生成脚本

```bash
#!/bin/bash
# generate-template.sh

TYPE=$1
NAME=$2
OUTPUT_DIR=${3:-.}

case $TYPE in
  component)
    PASCAL_NAME=$(echo "$NAME" | sed -E 's/(^|-)([a-z])/\U\2/g')
    cat > "$OUTPUT_DIR/$PASCAL_NAME.tsx" << 'TEMPLATE'
import React from 'react';

interface ${PASCAL_NAME}Props {
  // props
}

export const ${PASCAL_NAME}: React.FC<${PASCAL_NAME}Props> = (props) => {
  return (
    <div className="${NAME}">
      {/* content */}
    </div>
  );
};
TEMPLATE
    sed -i '' "s/\${PASCAL_NAME}/$PASCAL_NAME/g; s/\${NAME}/$NAME/g" "$OUTPUT_DIR/$PASCAL_NAME.tsx"
    echo "✓ Created $OUTPUT_DIR/$PASCAL_NAME.tsx"
    ;;
  *)
    echo "Unknown template type: $TYPE"
    ;;
esac
```

## 输出格式

```
┌─ 📄 Template Generated ─────────────────────────────────────────┐
│                                                                  │
│  Type: component                                                 │
│  Name: UserCard                                                  │
│  File: src/components/UserCard.tsx                               │
│                                                                  │
├─ Preview ────────────────────────────────────────────────────────┤
│                                                                  │
│  import React from 'react';                                      │
│                                                                  │
│  interface UserCardProps {                                       │
│    // props                                                      │
│  }                                                               │
│                                                                  │
│  export const UserCard: React.FC<UserCardProps> = ...            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Solar Skill 模板

用于创建新 Skill:

```bash
# 使用已有的 skill-gen.ts
bun run ~/.claude/skill-templates/skill-gen.ts \
  --type monitor \
  --name my-skill \
  --api "https://api.example.com"
```

## 扩展模板

在 `~/.claude/templates/` 目录下添加自定义模板:

```
~/.claude/templates/
├── component.tsx.tmpl
├── api.ts.tmpl
├── test.ts.tmpl
└── hook.ts.tmpl
```
