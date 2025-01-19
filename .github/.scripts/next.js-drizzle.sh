bunx create-next-app@latest awesomeDir --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd awesomeDir
bun add drizzle-orm drizzle-kit postgres

cat <<EOF >.env.local
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/postgres
EOF

cat <<EOF >drizzle.config.js
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
