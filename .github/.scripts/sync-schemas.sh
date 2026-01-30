mkdir awesomedir
bunx gitpick nrjdalal/awesome-templates/tree/main/next.js-apps/next.js-pro next.js-pro
cd next.js-pro
sed -i 's/import { magicLink } from "better-auth\/plugins"/import { magicLink, organization } from "better-auth\/plugins"/' src/lib/auth/index.ts
awk '
  { print }
  /magicLink\(\{/ { inMagicLink = 1 }
  /^    \}\),/ && inMagicLink {
    print "    organization({"
    print "      teams: { enabled: true },"
    print "    }),"
    inMagicLink = 0
  }
' src/lib/auth/index.ts >_ && mv _ src/lib/auth/index.ts
bun i && bunx @better-auth/cli generate --config src/lib/auth/index.ts -y
bunx prettier --write auth-schema.ts
cd ..
mv next.js-pro/auth-schema.ts awesomedir/drizzle-better-auth.ts
rm -rf next.js-pro
