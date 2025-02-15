bunx create-next-app@latest awesomedir --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd awesomedir
bunx shadcn@latest init -d <<EOF

EOF
bunx shadcn@latest add -a <<EOF

EOF
# custom best practices
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
bunx json -I -f package.json \
  -e 'this["lint-staged"]={"*": "prettier --write --ignore-unknown","package.json": "sort-package-json"}' \
  -e 'this["prettier"]={"semi": false,"plugins": ["@ianvs/prettier-plugin-sort-imports", "prettier-plugin-tailwindcss"]}' \
  -e 'this["commitlint"]={"extends": ["@commitlint/config-conventional"]}' \
  -e 'this.scripts.prepare="if [ -z \"$VERCEL_ENV\" ]; then simple-git-hooks; fi"' \
  -e 'this["simple-git-hooks"]={"pre-commit":"npx lint-staged --verbose","commit-msg":"npx commitlint --edit $1"}'
bunx sort-package-json
bunx prettier --write --ignore-unknown *
