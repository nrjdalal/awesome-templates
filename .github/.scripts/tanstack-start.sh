mkdir awesomedir && cd awesomedir
bunx gitpick nrjdalal/next-to-start/blob/main/.gitignore
bun add @tanstack/react-router@alpha @tanstack/react-start@alpha vite
bun add -D @tailwindcss/vite tailwindcss vite-tsconfig-paths
bunx fx package.json '{
  ...x,
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "start": "node .output/server/index.mjs"
  },
}' save
