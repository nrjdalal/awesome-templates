bunx create-next-app@latest app --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd app
bunx shadcn@latest init -d
bunx shadcn@latest add -a
bunx @tailwindcss/upgrade@next --force
