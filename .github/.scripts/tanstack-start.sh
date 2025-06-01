mkdir -p awesomedir/src/routes && cd awesomedir
bunx gitpick nrjdalal/next-to-start/blob/main/.gitignore
bun add react react-dom && bun add -D @types/node @types/react @types/react-dom typescript
bun add @tanstack/react-router@alpha @tanstack/react-start@alpha vite
bun add -D @tailwindcss/vite tailwindcss vite-tsconfig-paths
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
cat <<EOF >vite.config.ts
import tailwindcss from "@tailwindcss/vite"
import { tanstackStart } from "@tanstack/react-start/plugin/vite"
import { defineConfig } from "vite"
import tsConfigPaths from "vite-tsconfig-paths"

export default defineConfig({
  server: {
    port: 3000,
  },
  plugins: [
    tailwindcss(),
    tsConfigPaths(),
    tanstackStart(),
  ],
})
EOF
cat <<EOF >src/routes/globals.css
@import "tailwindcss";
EOF
cat <<EOF >src/routes/__root.tsx
import globalsCss from "./globals.css?url"
import {
  createRootRoute,
  HeadContent,
  Outlet,
  Scripts,
} from "@tanstack/react-router"

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: "utf-8",
      },
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1",
      },
      {
        title: "TanStack Start Starter",
      },
    ],
    links: [
      {
        rel: "stylesheet",
        href: globalsCss,
      },
    ],
  }),
  component: RootLayout,
})

function RootLayout() {
  return (
    <html>
      <head>
        <HeadContent />
      </head>
      <body>
        <Outlet />
        <Scripts />
      </body>
    </html>
  )
}
EOF
cat <<EOF >src/routes/index.tsx
export const Route = createFileRoute({
  component: Home,
})

function Home() {
  return (
    <main className="flex min-h-dvh w-screen flex-col items-center justify-center gap-y-4 p-4">
      <img
        className="w-full max-w-sm"
        src="https://tanstack.com/assets/splash-dark-8nwlc0Nt.png"
        alt="TanStack Logo"
      />
      <h1>
        <span className="line-through">Next.js</span> TanStack Start
      </h1>
      <a
        className="bg-foreground text-background rounded-full px-4 py-1 hover:opacity-90"
        href="https://tanstack.com/start/latest"
        target="_blank"
      >
        Docs
      </a>
    </main>
  )
}
EOF
cat <<EOF >src/router.tsx
import { createRouter as createTanStackRouter } from "@tanstack/react-router"
import { routeTree } from "./routeTree.gen"

export function createRouter() {
  const router = createTanStackRouter({
    routeTree,
    scrollRestoration: true,
  })
  return router
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createRouter>
  }
}
EOF
# do this stuff last
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
