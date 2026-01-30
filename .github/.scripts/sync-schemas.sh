mkdir awesomedir

# 1. drizzle-better-auth (base - no organization)
bunx gitpick nrjdalal/awesome-templates/tree/main/next.js-apps/next.js-pro next.js-pro
cd next.js-pro
bun i && bunx @better-auth/cli generate --config src/lib/auth/index.ts -y
bunx prettier --write auth-schema.ts
cd ..
mv next.js-pro/auth-schema.ts awesomedir/drizzle-better-auth.ts
rm -rf next.js-pro

# 2. drizzle-better-auth-organization (organization without teams)
bunx gitpick nrjdalal/awesome-templates/tree/main/next.js-apps/next.js-pro next.js-pro
cd next.js-pro
sed -i '' 's/import { magicLink } from "better-auth\/plugins"/import { magicLink, organization } from "better-auth\/plugins"/' src/lib/auth/index.ts
awk '
  { print }
  /magicLink\(\{/ { inMagicLink = 1 }
  /^    \}\),/ && inMagicLink {
    print "    organization(),"
    inMagicLink = 0
  }
' src/lib/auth/index.ts >_ && mv _ src/lib/auth/index.ts
bun i && bunx @better-auth/cli generate --config src/lib/auth/index.ts -y
bunx prettier --write auth-schema.ts
cd ..
mv next.js-pro/auth-schema.ts awesomedir/drizzle-better-auth-organization.ts
rm -rf next.js-pro

# 3. drizzle-better-auth-team (organization with teams enabled)
bunx gitpick nrjdalal/awesome-templates/tree/main/next.js-apps/next.js-pro next.js-pro
cd next.js-pro
sed -i '' 's/import { magicLink } from "better-auth\/plugins"/import { magicLink, organization } from "better-auth\/plugins"/' src/lib/auth/index.ts
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
mv next.js-pro/auth-schema.ts awesomedir/drizzle-better-auth-team.ts
rm -rf next.js-pro

