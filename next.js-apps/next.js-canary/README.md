Generated using: ```sh
bunx create-next-app@canary "$TEMP_DIR" --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*"
cd "$TEMP_DIR"

# custom best practices
bun add -D @commitlint/cli @commitlint/config-conventional lint-staged prettier prettier-plugin-organize-imports prettier-plugin-tailwindcss simple-git-hooks sort-package-json
cat <<EOF >.lintstagedrc
{
  "*": ["prettier --write --ignore-unknown"],
  "package.json": ["sort-package-json"]
}
EOF
cat <<EOF >.prettierrc
{
  "semi": false,
  "plugins": ["prettier-plugin-organize-imports", "prettier-plugin-tailwindcss"]
}
EOF
cat <<EOF >.commitlintrc
{
  "extends": [
    "@commitlint/config-conventional"
  ]
}
EOF
bunx json -I -f package.json -e 'this.scripts.prepare="if [ -z \"$VERCEL_ENV\" ]; then simple-git-hooks; fi"'
bunx json -I -f package.json -e 'this["simple-git-hooks"]={"pre-commit":"npx lint-staged --verbose","commit-msg":"npx commitlint --edit $1"}'
bunx sort-package-json
bunx prettier --write --ignore-unknown *
```
