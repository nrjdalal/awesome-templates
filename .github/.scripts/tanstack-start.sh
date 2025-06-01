mkdir awesomedir && cd awesomedir
bunx gitpick nrjdalal/next-to-start/blob/main/.gitignore
bun add @tanstack/react-router@alpha @tanstack/react-start@alpha vite
bun add -D @tailwindcss/vite tailwindcss vite-tsconfig-paths
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
bunx fx package.json '{
  ...x,
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "start": "node .output/server/index.mjs",
    "prepare": "npx simple-git-hooks",
    "drizzle": "bun --env-file=.env.development drizzle-kit push",
    "drizzle:prod": "bun --env-file=.env.production drizzle-kit push",
    "studio": "bun --env-file=.env.development drizzle-kit studio",
    "studio:prod": "bun --env-file=.env.production drizzle-kit studio",
  },
  "simple-git-hooks": {
    "pre-commit": "npx lint-staged --verbose",
    "commit-msg": "npx commitlint --edit $1"
  },
  "commitlint": {
    "extends": [
      "@commitlint/config-conventional"
    ]
  },
  "lint-staged": {
    "*": "prettier --write --ignore-unknown",
    "package.json": "sort-package-json"
  },
  "prettier": {
    "importOrder": [
      "<BUILTIN_MODULES>",
      "",
      "^react/(.*)$|^react$",
      "^@tanstack/(.*)$|^@tanstack$",
      "",
      "<THIRD_PARTY_MODULES>",
      "",
      "^@/types/(.*)$",
      "^@/config/(.*)$",
      "^@/lib/(.*)$",
      "^@/hooks/(.*)$",
      "^@/db/(.*)$",
      "^@/components/ui/(.*)$",
      "^@/components/(.*)$",
      "^@/app/(.*)$",
      "^@/routes/(.*)$",
      "",
      "^[./]"
    ],
    "plugins": [
      "@ianvs/prettier-plugin-sort-imports",
      "prettier-plugin-tailwindcss"
    ],
    "printWidth": 100,
    "semi": false
  },
}' save
bunx sort-package-json@latest
bunx prettier@latest --write --ignore-unknown *
