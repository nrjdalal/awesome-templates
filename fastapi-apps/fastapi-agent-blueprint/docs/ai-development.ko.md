# AI 네이티브 개발 가이드

> 간략한 개요는 [README](README.ko.md#ai-네이티브-개발)를 참고하세요.

## 구조

이 레포지토리는 **공통 규칙 + 공통 레퍼런스 + 도구별 하네스** 구조를 사용합니다:

| 파일 | 역할 |
|------|------|
| `AGENTS.md` | 모든 AI 도구가 따라야 하는 공통 규칙의 canonical source |
| `docs/ai/shared/` | Claude와 Codex가 함께 읽는 공통 workflow 레퍼런스와 체크리스트 |
| `CLAUDE.md` | Claude 전용 hooks, plugins, slash skills, workflow 안내 |
| `.mcp.json` | Claude 전용 MCP 설정 |
| `.codex/config.toml` | Codex CLI 전용 프로젝트 설정, profile, feature, MCP 구성 |
| `.codex/hooks.json` | Codex 명령 훅 설정 |
| `.agents/skills/` | repo-local Codex workflow skill |

## 공통 규칙 우선

모든 도구는 먼저 `AGENTS.md`를 기준으로 다음을 따른다:
- 프로젝트 규모 전제
- 절대 금지 규칙
- 레이어 용어와 conversion pattern
- DTO 생성 기준
- 기본 run/test/lint/migration 명령
- 문서와 규칙 drift 관리 원칙

루트 `AGENTS.md`에 다 담기 어려운 workflow 세부사항은 `docs/ai/shared/`에 둡니다. 예: `project-dna.md`, planning/security/review checklist, test pattern. `/sync-guidelines` 또는 `$sync-guidelines`를 실행할 때는 수동 검토 항목이 빠지지 않도록 최종 결과에 `project-dna`, `AUTO-FIX`, `REVIEW`, `Remaining`를 모두 명시해야 합니다.

## Claude Code

### 플러그인 설정 (필수)

코드 인텔리전스(심볼 탐색, 참조 추적, 진단)를 위해 pyright-lsp 플러그인을 설치하세요:

```bash
uv sync                              # pyright 바이너리 설치 (dev 의존성)
claude plugin install pyright-lsp    # Claude Code 플러그인 설치
```

> `.claude/settings.json`의 `enabledPlugins`가 첫 실행 시 자동으로 설치를 안내합니다.

### MCP 서버 설정 (`.mcp.json`)

**context7** -- 라이브러리 최신 문서 조회
```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp"
    }
  }
}
```

> `.mcp.json`은 Claude 측 MCP 진입점입니다. MCP 서버 없이도 프로젝트 자체는 정상 동작하지만, Claude 스킬은 이 설정을 기대합니다.

## Codex CLI

Codex는 `.codex/config.toml`의 project-shared 설정을 사용합니다:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
web_search = "disabled"

[features]
codex_hooks = true

[profiles.research]
web_search = "live"

[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"
```

> Codex는 원격 Context7 MCP 엔드포인트를 사용합니다. 로컬 stdio 서버(npx) 방식은 샌드박스 네트워크 제한에 의해 차단되므로, HTTP 전송 방식을 사용합니다.

Codex의 레포 workflow layer는 다음으로 나뉩니다:
- `.codex/config.toml` — base config와 profile
- `.codex/hooks.json` + `.codex/hooks/` — command hook
- `.agents/skills/` — `$onboard`, `$plan-feature`, `$review-pr` 같은 repo-local workflow
- `docs/ai/shared/` — Claude/Codex 공통 reference

권장 검증 흐름:
1. Codex에서 이 프로젝트를 trusted 상태로 만든다.
2. `codex mcp list`, `codex mcp get context7`를 실행한다.
3. `codex debug prompt-input -c 'project_doc_max_bytes=400' "healthcheck" | rg "Shared Collaboration Rules|AGENTS\\.md"`로 `AGENTS.md`가 실제 prompt input에 포함되는지 확인한다.
4. 최신 외부 정보가 정말 필요할 때만 `codex -p research` 또는 `codex --search`를 사용한다.
5. Codex memories는 개인/세션 최적화용으로만 보고, 팀 규칙 저장소로 쓰지 않는다.

> `.codex/config.toml`은 Codex 측 하네스 진입점입니다. 웹 검색은 기본 비활성화되어 있으므로, 최신 외부 정보가 필요할 때만 명시적으로 활성화하세요.
