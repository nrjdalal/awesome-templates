mkdir awesomedir
bunx gitpick nrjdalal/awesome-templates/tree/main/next.js-apps/next.js-pro next.js-pro
cd next.js-pro
bun i && bunx @better-auth/cli generate --config src/lib/auth/index.ts -y
bunx prettier --write auth-schema.ts
cd ..
mv next.js-pro/auth-schema.ts awesomedir/drizzle-better-auth.ts
rm -rf next.js-pro
