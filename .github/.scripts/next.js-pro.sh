bunx create-next-app@latest --ts --eslint --tailwind --src-dir --app --turbopack --import-alias "@/*" awesomedir
cd awesomedir
bunx shadcn@latest init --base-color neutral -d
# add better-auth
bunx shadcn@latest add https://raw.githubusercontent.com/nrjdalal/the-next-starter/refs/heads/main/public/r/app-api-auth.json
# add next-theme sonner tanstack-query
bunx shadcn@latest add https://raw.githubusercontent.com/nrjdalal/the-next-starter/refs/heads/main/public/r/app-providers.json
bunx shadcn@latest add -a -o
bunx colorwindcss@latest
awk 'NR == 1 { print; print "import { InnerProvider, OuterProvider } from \"@/app/providers\"" } NR > 1' src/app/layout.tsx >_ && mv _ src/app/layout.tsx
sed -i \
  -e 's/font-\[family-name:[^]]*\] *//g' \
  src/app/page.tsx
sed -i \
  -e '/import { Geist, Geist_Mono }.*/d' \
  -e '/const geistSans = Geist({/,/})/d' \
  -e '/const geistMono = Geist_Mono({/,/})/d' \
  -e 's/lang="en">/lang="en" suppressHydrationWarning>/' \
  -e 's/\${geistSans.variable} //g' \
  -e 's/\${geistMono.variable} //g' \
  -e 's/{`antialiased`}/"min-h-dvh antialiased"/g' \
  -e 's|<html|<OuterProvider><html|' \
  -e 's|{children}|<InnerProvider>{children}</InnerProvider>|' \
  -e 's|/html>|/html></OuterProvider>|' \
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
bun add -D @commitlint/cli @commitlint/config-conventional @fontsource-variable/dm-sans @fontsource-variable/jetbrains-mono @ianvs/prettier-plugin-sort-imports lint-staged prettier prettier-plugin-tailwindcss simple-git-hooks sort-package-json
echo "$(bunx fx package.json '{
  ...x,
  "scripts": {
    ...x.scripts,
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
    "plugins": [
      "@ianvs/prettier-plugin-sort-imports",
      "prettier-plugin-tailwindcss"
    ],
    "semi": false
  },
}')" >package.json
bunx sort-package-json
bunx prettier --write --ignore-unknown *
