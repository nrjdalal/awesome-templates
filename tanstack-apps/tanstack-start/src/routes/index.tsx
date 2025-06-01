export const Route = createFileRoute({
  component: Component,
})

function Component() {
  return (
    <main className="flex min-h-dvh w-screen flex-col items-center justify-center gap-y-4 p-4">
      <img
        className="aspect-square w-full max-w-sm"
        src="https://tanstack.com/assets/splash-dark-8nwlc0Nt.png"
        alt="TanStack Logo"
      />
      <h1>TanStack Start</h1>
      <a
        className="rounded-full border px-4 py-1 hover:opacity-90"
        href="https://tanstack.com/start/latest"
        target="_blank"
      >
        Docs
      </a>
    </main>
  )
}
