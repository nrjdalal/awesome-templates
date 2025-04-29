bunx create-next-app@latest --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*" awesomedir
cd awesomedir
cat <<EOF >drizzle.config.ts
import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.POSTGRES_URL!,
  },
  schema: './src/db',
  out: './src/db/drizzle',
})
EOF
mkdir -p src/db
cat <<EOF >src/db/index.ts
import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js"
import postgres from "postgres"

declare global {
  // eslint-disable-next-line
  var db: PostgresJsDatabase
}

let db: PostgresJsDatabase

if (process.env.NODE_ENV === "production") {
  db = drizzle({
    client: postgres(process.env.POSTGRES_URL!, {
      connect_timeout: 10000,
      idle_timeout: 30000,
      ssl: {
        rejectUnauthorized: true,
      },
    }),
  })
} else {
  if (!global.db) {
    global.db = drizzle({
      client: postgres(process.env.POSTGRES_URL!, {
        connect_timeout: 10000,
        idle_timeout: 30000,
      }),
    })
  }
  db = global.db
}

export { db }
EOF
# custom best practices
bun add drizzle-orm postgres
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports drizzle-kit lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
echo "$(bunx fx package.json '{
  ...x,
  "scripts": {
    ...x.scripts,
    "prepare": "npx simple-git-hooks",
    "drizzle": "bun --env-file=.env.development drizzle-kit push",
    "studio": "bun --env-file=.env.development drizzle-kit studio",
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
    "plugins": [
      "@ianvs/prettier-plugin-sort-imports",
      "prettier-plugin-tailwindcss"
    ],
    "semi": false
  },
}')" >package.json
bunx sort-package-json
bunx prettier --write --ignore-unknown *
