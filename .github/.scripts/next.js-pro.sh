bunx create-next-app@latest --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*" awesomedir
cd awesomedir
bunx shadcn@latest init --base-color neutral -d
bunx shadcn@latest add -a
bunx colorwindcss@latest
# custom best practices
bun add -D @commitlint/cli @commitlint/config-conventional @fontsource-variable/dm-sans @fontsource-variable/jetbrains-mono @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
sed -i '' \
  -e '/import { Geist, Geist_Mono }.*/d' \
  -e '/const geistSans = Geist({/,/})/d' \
  -e '/const geistMono = Geist_Mono({/,/})/d' \
  -e 's/lang="en"/lang="en" suppressHydrationWarning/' \
  -e 's/${geistSans.variable} //g' \
  -e 's/${geistMono.variable} //g' \
  src/app/layout.tsx
awk '
  /@import/ { l = NR }
  {
    if ($0 ~ /--font-sans:/) sub(/: .*/, ": \"DM Sans Variable\", sans-serif;");
    if ($0 ~ /--font-mono:/) sub(/: .*/, ": \"JetBrains Mono Variable\", monospace;");
    a[NR] = $0
  }
  END {
    for (i = 1; i <= NR; i++) {
      print a[i]
      if (i == l) {
        print "@import \"@fontsource-variable/dm-sans\";"
        print "@import \"@fontsource-variable/jetbrains-mono\";"
      }
    }
  }
' src/app/globals.css >_ && mv _ src/app/globals.css
echo "$(bunx fx package.json '{
  ...x,
  "scripts": {
    ...x.scripts,
    "prepare": "npx simple-git-hooks",
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
