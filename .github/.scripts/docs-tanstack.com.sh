bunx gitpick https://github.com/TanStack/tanstack.com awesomedir
cd awesomedir
sed -i "s/const repo = 'tanstack/router'/const repo = 'nrjdalal/router'/g" src/libraries/router.tsx
sed -i "s/const repo = 'tanstack/router'/const repo = 'nrjdalal/router'/g" src/libraries/start.tsx
sed -i "s/latestBranch: 'main'/latestBranch: 'preview-alpha'/g" src/libraries/router.tsx
sed -i "s/latestBranch: 'main'/latestBranch: 'preview-alpha'/g" src/libraries/start.tsx
