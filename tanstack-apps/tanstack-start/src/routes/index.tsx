export const Route = createFileRoute({
  component: Component,
})

function Component() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-y-4 bg-radial from-cyan-950 to-black p-4 text-gray-100">
      <img
        className="aspect-square w-full max-w-sm"
        src="https://tanstack.com/assets/splash-dark-8nwlc0Nt.png"
        alt="TanStack Logo"
      />
      <h1 className="text-2xl">
        <span className="font-semibold">TanStack</span>
        &nbsp;
        <span className="text-cyan-500">Start</span>
      </h1>
      <a
        className="rounded-full bg-gray-100 px-4 py-1 text-gray-900 hover:opacity-90"
        href="https://tanstack.com/start/latest"
        target="_blank"
      >
        Docs
      </a>
    </main>
  )
}
