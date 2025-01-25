bunx create-next-app@latest awesomedir --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd awesomedir
bunx shadcn@latest init -d
bunx shadcn@latest add -a
bunx @tailwindcss/upgrade@next --force
