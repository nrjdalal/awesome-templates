mkdir awesomedir
bunx gitpick nrjdalal/awesome-templates/tree/main/next.js-apps/next.js-pro next.js-pro
cd next.js-pro
cat <<EOF >src/lib/auth/index.ts
import { db } from "@/db"
import { betterAuth } from "better-auth"
import { drizzleAdapter } from "better-auth/adapters/drizzle"
import { nextCookies } from "better-auth/next-js"
import { magicLink, organization } from "better-auth/plugins"
import { Resend } from "resend"

import { account, session, user, verification } from "@/db/schema/auth"

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "pg",
    schema: {
      user,
      session,
      account,
      verification,
    },
  }),
  socialProviders: {
    github: {
      clientId: process.env.GITHUB_CLIENT_ID as string,
      clientSecret: process.env.GITHUB_CLIENT_SECRET as string,
    },
  },
  plugins: [
    nextCookies(),
    magicLink({
      sendMagicLink: async ({ email, url }) => {
        const resend = new Resend(process.env.RESEND_API_KEY as string)

        await resend.emails.send({
          from: "ACME Inc. <onboarding@tns.nrjdalal.com>",
          to: [email],
          subject: "Verify your email address",
          html: `Click the link to verify your email: ${url}`,
        })
      },
    }),
    organization({
      teams: { enabled: true },
    }),
  ],
})
EOF
bun i && bunx @better-auth/cli generate --config src/lib/auth/index.ts -y
bunx prettier --write auth-schema.ts
cd ..
mv next.js-pro/auth-schema.ts awesomedir/drizzle-better-auth.ts
rm -rf next.js-pro
