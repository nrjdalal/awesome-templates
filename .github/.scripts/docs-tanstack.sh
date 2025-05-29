bunx gitpick https://github.com/TanStack/tanstack.com awesomedir
cd awesomedir
# need to change latestBranch: 'main' to latestBranch: 'alpha' in src/libraries/router.tsx and src/libraries/start.tsx using sed
sed -i 's/latestBranch: "main"/latestBranch: "alpha"/g' src/libraries/router.tsx
sed -i 's/latestBranch: "main"/latestBranch: "alpha"/g' src/libraries/start.tsx
