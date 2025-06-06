bunx gitpick https://github.com/nrjdalal/tanstack.com -b revamp awesomedir
cd awesomedir
# sed -i "s/latestBranch: 'main'/latestBranch: 'alpha'/g" src/libraries/router.tsx
# sed -i "s/latestBranch: 'main'/latestBranch: 'alpha'/g" src/libraries/start.tsx
## router/start alpha docs
bunx gitpick https://github.com/TanStack/router/tree/alpha/docs router-docs
bunx gitpick https://github.com/nrjdalal/router/blob/guide-to-integrate-better-auth/docs/start/framework/react/integrate-better-auth.md router-docs/start/framework/react
jq '.sections |= (
    .[:1]
  + [
      {
        "label": "Guides",
        "children": [],
        "frameworks": [
          {
            "label": "react",
            "children": [
              {
                "label": "Integrate Better Auth",
                "to": "framework/react/integrate-better-auth"
              }
            ]
          }
        ]
      }
    ]
  + .[1:]
)' router-docs/start/config.json >tmp && mv tmp router-docs/start/config.json
sed -i "s/const repo = 'tanstack\/router'/const repo = 'nrjdalal\/awesome-templates'/g" src/libraries/router.tsx
sed -i "s/const repo = 'tanstack\/router'/const repo = 'nrjdalal\/awesome-templates'/g" src/libraries/start.tsx
sed -i "s/docsRoot: 'docs\/router'/docsRoot: 'docs-apps\/docs-tanstack.com\/router-docs\/router'/g" src/libraries/router.tsx
sed -i "s/docsRoot: 'docs\/start'/docsRoot: 'docs-apps\/docs-tanstack.com\/router-docs\/start'/g" src/libraries/start.tsx
