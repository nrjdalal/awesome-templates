# Awesome Template

[![Twitter](https://img.shields.io/twitter/follow/nrjdalal_com?label=%40nrjdalal_com)](https://twitter.com/nrjdalal_com) [![Awesome](https://awesome.re/badge.svg)](https://github.com/nrjdalal/awesome-templates) [![GitHub](https://img.shields.io/github/stars/nrjdalal/awesome-templates?color=blue)](https://github.com/nrjdalal/awesome-templates)

This template is bootstrapped with script [vite-qwik.sh](https://github.com/nrjdalal/awesome-templates/blob/main/.github/.scripts/vite-qwik.sh) and is part of the [awesome-templates](https://github.com/nrjdalal/awesome-templates) repository, to explore a curated collection of up-to-date templates for various projects and frameworks, refreshed every 8 hours.

## Clone this template

```bash
npx gitpick@latest nrjdalal/awesome-templates/tree/main/vite-apps/vite-qwik
```

If you wish to make changes to this template or add your own, please refer to the [contribution guidelines](https://github.com/nrjdalal/awesome-templates?tab=readme-ov-file#contributing).

---

# Qwik + Vite

## Qwik in CSR mode

This starter is using a pure CSR (Client-Side Rendering) mode. This means, that the application is fully bootstrapped in the browser. Most of Qwik innovations however take advantage of SSR (Server-Side Rendering) mode.

```ts
export default defineConfig({
  plugins: [
    qwikVite({
      csr: true,
    }),
  ],
})
```

Use `npm create qwik@latest` to create a full production ready Qwik application, using SSR and [QwikCity](https://qwik.dev/docs/qwikcity/), our server-side metaframwork.

## Usage

```bash
$ npm install # or pnpm install or yarn install
```

Learn more on the [Qwik Website](https://qwik.dev) and join our community on our [Discord](https://qwik.dev/chat)

## Available Scripts

In the project directory, you can run:

### `npm run dev`

Runs the app in the development mode.<br>
Open [http://localhost:5173](http://localhost:5173) to view it in the browser.

### `npm run build`

Builds the app for production to the `dist` folder.<br>
