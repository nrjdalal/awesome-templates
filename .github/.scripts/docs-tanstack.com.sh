bunx gitpick https://github.com/TanStack/tanstack.com awesomedir
cd awesomedir
sed -i "s/const repo = 'tanstack\/router'/const repo = 'nrjdalal\/awesome-templates'/g" src/libraries/router.tsx
sed -i "s/const repo = 'tanstack\/router'/const repo = 'nrjdalal\/awesome-templates'/g" src/libraries/start.tsx
sed -i "s/docsRoot: 'docs\/router'/docsRoot: 'docs-apps\/docs-tanstack-router\/docs\/router'/g" src/libraries/router.tsx
sed -i "s/docsRoot: 'docs\/start'/docsRoot: 'docs-apps\/docs-tanstack-router\/docs\/start'/g" src/libraries/start.tsx
