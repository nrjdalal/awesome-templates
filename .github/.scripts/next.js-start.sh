bunx create-next-app@latest --ts --tailwind --src-dir --app --turbopack --import-alias "@/*" awesomedir
cd awesomedir
cat <<EOF >src/app/page.tsx
export default function Home() {
  return (
    <main className="min-h-dvh w-screen flex items-center justify-center flex-col gap-y-4 p-4">
      <img
        className="max-w-sm w-full"
        src="https://tanstack.com/assets/splash-dark-8nwlc0Nt.png"
        alt="TanStack Logo"
      />
      <h1>
        <span className="line-through">Next.js</span> TanStack Start
      </h1>
      <a
        className="bg-foreground text-background rounded-full px-4 py-1 hover:opacity-90"
        href="https://tanstack.com/start/latest"
        target="_blank"
      >
        Docs
      </a>
    </main>
  )
}
EOF
# custom updates to the README.md
PREPEND="## This is a starter template to test migration of Next.js to TanStack Start

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
