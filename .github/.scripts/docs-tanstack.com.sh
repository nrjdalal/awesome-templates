bunx gitpick https://github.com/TanStack/tanstack.com awesomedir
cd awesomedir
bunx gitpick https://github.com/TanStack/router/tree/alpha/docs router-docs
bunx gitpick https://github.com/nrjdalal/router/blob/migrate-from-next-js-app-router/docs/start/framework/react/migrate-from-next-js.md router-docs/start/framework/react
sed -i "s/const repo = 'tanstack\/router'/const repo = 'nrjdalal\/awesome-templates'/g" src/libraries/router.tsx
sed -i "s/const repo = 'tanstack\/router'/const repo = 'nrjdalal\/awesome-templates'/g" src/libraries/start.tsx
sed -i "s/docsRoot: 'docs\/router'/docsRoot: 'docs-apps\/docs-tanstack.com\/router-docs\/router'/g" src/libraries/router.tsx
sed -i "s/docsRoot: 'docs\/start'/docsRoot: 'docs-apps\/docs-tanstack.com\/router-docs\/start'/g" src/libraries/start.tsx
