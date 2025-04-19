bunx create-next-app@latest --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*" awesomedir
cd awesomedir
bunx shadcn@latest init -d
# hack if the command above fails
[ ! -f components.json ] && bunx shadcn@latest init <<EOF

EOF
bunx shadcn@latest add -a
# hack to move devDependencies from dependencies to devDependencies
echo "$(bunx fx package.json 'x => { if (x.dependencies["tw-animate-css"]) { const version = x.dependencies["tw-animate-css"]; delete x.dependencies["tw-animate-css"]; x.devDependencies["tw-animate-css"] = version; } return x; }')" >package.json
# custom best practices
bun add -D @commitlint/cli @commitlint/config-conventional @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
echo "$(bunx fx package.json '{
  ...x,
  "scripts": {
    ...x.scripts,
    "prepare": "simple-git-hooks",
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
