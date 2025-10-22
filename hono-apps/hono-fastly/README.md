# Awesome Template

[![Twitter](https://img.shields.io/twitter/follow/nrjdalal_com?label=%40nrjdalal_com)](https://twitter.com/nrjdalal_com) [![Awesome](https://awesome.re/badge.svg)](https://github.com/nrjdalal/awesome-templates) [![GitHub](https://img.shields.io/github/stars/nrjdalal/awesome-templates?color=blue)](https://github.com/nrjdalal/awesome-templates)

This template is bootstrapped with script [hono-fastly.sh](https://github.com/nrjdalal/awesome-templates/blob/main/.github/.scripts/hono-fastly.sh) and is part of the [awesome-templates](https://github.com/nrjdalal/awesome-templates) repository, to explore a curated collection of up-to-date templates for various projects and frameworks, refreshed every 8 hours.

## Clone this template

```bash
npx gitpick@latest nrjdalal/awesome-templates/tree/main/hono-apps/hono-fastly
```

If you wish to make changes to this template or add your own, please refer to the [contribution guidelines](https://github.com/nrjdalal/awesome-templates?tab=readme-ov-file#contributing).

---

```
npm install
npm run start
```

```
open http://localhost:7676
```

```
npm run deploy
```

For [typed bindings based on your Fastly resources](https://github.com/fastly/hono-fastly-compute?tab=readme-ov-file#basic-example):

Import `buildFire` instead of `fire` from `@fastly/hono-fastly-compute`, and define your resources. Then pass `fire.Bindings` as the generic parameter when instantiating `Hono`:

```ts
// src/index.ts
import { buildFire } from '@fastly/hono-fastly-compute'
const fire = buildFire({
  assets: 'KVStore', // A KV Store named 'assets'
  mySettings: 'ConfigStore:my-settings' // A Config Store named 'my-settings'
})
const app = new Hono<{ Bindings: fire.Bindings }>()
```
