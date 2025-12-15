bunx create-next-app@latest --ts --tailwind --react-compiler --eslint --app --src-dir --turbopack --import-alias "@/*" awesomedir
cd awesomedir
bunx shadcn@latest init --base-color neutral -d
bunx shadcn@latest add https://raw.githubusercontent.com/nrjdalal/the-next-starter/refs/heads/main/public/r/better-auth.json
bunx shadcn@latest add https://raw.githubusercontent.com/nrjdalal/the-next-starter/refs/heads/main/public/r/providers.json
bunx shadcn@latest add -a -o
bunx shadcn@latest migrate radix -y
bunx smart-registry@latest
find public/r -type f ! -name 'ui.json' -delete
bunx colorwindcss@latest
awk 'NR == 1 { print; print "import Navbar from \"@/components/navbar/home\"\nimport { InnerProvider, OuterProvider } from \"@/app/providers\"" } NR > 1' src/app/layout.tsx >_ && mv _ src/app/layout.tsx
sed -i \
  -e '/import { Geist, Geist_Mono }.*/d' \
  -e '/const geistSans = Geist({/,/})/d' \
  -e '/const geistMono = Geist_Mono({/,/})/d' \
  -e 's/lang="en">/lang="en" suppressHydrationWarning>/' \
  -e 's/\${geistSans.variable} //g' \
  -e 's/\${geistMono.variable} //g' \
  -e 's/{`antialiased`}/"min-h-dvh antialiased"/g' \
  -e 's|<html|<OuterProvider><html|' \
  -e 's|{children}|<InnerProvider><Navbar/>{children}</InnerProvider>|' \
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
bunx fx package.json '{
  ...x,
  "scripts": {
    ...x.scripts,
    "prepare": "npx simple-git-hooks",
    "db:push": "bun --env-file=.env.development drizzle-kit push",
    "db:push:prod": "bun --env-file=.env.production drizzle-kit push",
    "db:pull": "bun --env-file=.env.development drizzle-kit pull",
    "db:pull:prod": "bun --env-file=.env.production drizzle-kit pull",
    "db:studio": "bun --env-file=.env.development drizzle-kit studio",
    "db:studio:prod": "bun --env-file=.env.production drizzle-kit studio",
    "db:migrate": "bun --env-file=.env.development drizzle-kit migrate",
    "db:migrate:prod": "bun --env-file=.env.production drizzle-kit migrate",
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
    "importOrder": [
      "<BUILTIN_MODULES>",
      "",
      "^react/(.*)$|^react$",
      "^next/(.*)$|^next$",
      "",
      "<THIRD_PARTY_MODULES>",
      "",
      "^@/types/(.*)$",
      "^@/config/(.*)$",
      "^@/lib/(.*)$",
      "^@/hooks/(.*)$",
      "^@/db/(.*)$",
      "^@/components/ui/(.*)$",
      "^@/components/(.*)$",
      "^@/app/(.*)$",
      "",
      "^[./]"
    ],
    "plugins": [
      "@ianvs/prettier-plugin-sort-imports",
      "prettier-plugin-tailwindcss"
    ],
    "printWidth": 100,
    "semi": false
  },
}' save
bunx sort-package-json@latest
bunx prettier@latest --write --ignore-unknown *
# shadcn@latest stopped updating the import paths in the code, hacking it for now
# find . -type f \( -name '*.ts' -o -name '*.tsx' \) -exec sed -i 's|from "/|from "@/|g' {} +
# custom updates for the README.md
PREPEND="## Update the UI components

\`\`\`sh
npx shadcn@latest add -o https://dub.sh/ui.json
\`\`\`

---
"
if ! ls | grep -iq "^readme\.md$"; then
  echo "${PREPEND}" >"README.md"
else
  {
    echo "${PREPEND}"
    cat "$(ls | grep -i "^readme\.md$")"
  } >temp_readme.md && mv temp_readme.md "README.md"
fi
