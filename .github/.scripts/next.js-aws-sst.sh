bunx create-next-app@latest awesomedir --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd awesomedir
bunx sst@latest init --yes
# custom best practices
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
echo "$(bunx fx package.json '{
  ...x,
  "scripts": {
    ...x.scripts,
    "prepare": "if [ -z \"$VERCEL_ENV\" ]; then simple-git-hooks; fi",
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
