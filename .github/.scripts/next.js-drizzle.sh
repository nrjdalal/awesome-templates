bunx create-next-app@latest awesomedir --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd awesomedir
bun add drizzle-orm drizzle-kit postgres
cat <<EOF >.env.local
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/postgres
EOF
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
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
bunx json -I -f package.json \
  -e 'this.scripts.prepare="if [ -z \"$VERCEL_ENV\" ]; then simple-git-hooks; fi"' \
  -e 'this["simple-git-hooks"]={"pre-commit":"npx lint-staged --verbose","commit-msg":"npx commitlint --edit $1"}' \
  -e 'this["commitlint"]={"extends":["@commitlint/config-conventional"]}' \
  -e 'this["lint-staged"]={"*":"prettier --write --ignore-unknown","package.json":"sort-package-json"}' \
  -e 'this["prettier"]={"semi":false,"plugins":["@ianvs/prettier-plugin-sort-imports","prettier-plugin-tailwindcss"]}'
bunx sort-package-json
bunx prettier --write --ignore-unknown *
