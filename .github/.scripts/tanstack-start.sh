mkdir -p awesomedir/src/routes && cd awesomedir
bunx gitpick nrjdalal/next-to-start/blob/main/.gitignore
bun add react react-dom && bun add -D @types/node @types/react @types/react-dom typescript
bun add @tanstack/react-router@alpha @tanstack/react-start@alpha vite
bun add -D @tailwindcss/vite tailwindcss vite-tsconfig-paths
bun add -D prettier prettier-plugin-tailwindcss
cat <<EOF >tsconfig.json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "types": ["vite/client"],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
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
  component: Component,
})

function Component() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-y-4 bg-radial from-cyan-950 to-black p-4 text-gray-100">
      <img
        className="aspect-square w-full max-w-sm"
        src="https://tanstack.com/assets/splash-dark-8nwlc0Nt.png"
        alt="TanStack Logo"
      />
      <h1 className="text-2xl">
        <span className="font-semibold">TanStack</span>
        &nbsp;
        <span className="text-cyan-500">Start</span>
      </h1>
      <a
        className="rounded-full bg-gray-100 px-4 py-1 text-gray-900 hover:opacity-90"
        href="https://tanstack.com/start/latest"
        target="_blank"
      >
        Docs
      </a>
    </main>
  )
}
EOF
bunx fx package.json '{
  ...x,
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "start": "node .output/server/index.mjs",
  },
  "prettier": {
    "plugins": [
      "prettier-plugin-tailwindcss"
    ],
    "printWidth": 100,
    "semi": false
  },
}' save
bunx sort-package-json@latest
bunx prettier@latest --write --ignore-unknown *
