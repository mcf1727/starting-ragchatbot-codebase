# Frontend Changes

## Code Quality Tooling

Added code quality tooling to the frontend development workflow.

### New Files

| File | Purpose |
|------|---------|
| `frontend/package.json` | npm manifest with `format`, `format:check`, `lint`, `lint:fix`, `check`, and `fix` scripts |
| `frontend/.prettierrc` | Prettier configuration (2-space indent, single quotes, trailing commas, LF line endings) |
| `frontend/.eslintrc.json` | ESLint configuration (browser globals, ES2021, `marked` as a read-only global, `no-var`/`prefer-const` enforced) |
| `scripts/check-frontend.sh` | Root-level shell script that runs Prettier check + ESLint from anywhere in the project |
| `scripts/fix-frontend.sh` | Root-level shell script that auto-applies Prettier formatting and ESLint fixes |

### Modified Files

| File | Change |
|------|--------|
| `frontend/script.js` | Reformatted by Prettier: 4-space → 2-space indentation, trailing commas in multi-line objects/arrays, consistent arrow-function parens |
| `frontend/style.css` | Reformatted by Prettier: consistent property spacing and declaration order |
| `frontend/index.html` | Reformatted by Prettier: consistent attribute quoting and indentation |
| `.gitignore` | Added `frontend/node_modules/` exclusion |

### Usage

From the project root:

```bash
# Check formatting and lint (read-only, safe for CI)
bash scripts/check-frontend.sh

# Auto-fix all formatting and lint issues
bash scripts/fix-frontend.sh
```

Or directly inside `frontend/`:

```bash
cd frontend
npm run check        # format:check + lint
npm run fix          # format + lint:fix
npm run format       # Prettier write only
npm run lint         # ESLint only
```

### Tools

- **Prettier 3.3** — automatic, opinionated formatting for JS, CSS, and HTML
- **ESLint 8.57** — static analysis for `script.js`; enforces `const`/`let` over `var`, strict equality, and warns on raw `console` calls
