bunx gitpick https://github.com/TanStack/router/tree/alpha/docs awesomedir/docs
cd awesomedir
bunx gitpick https://github.com/nrjdalal/router/blob/migrate-from-next-js-app-router/docs/start/framework/react/migrate-from-next-js.md docs/start/framework/react
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
                "label": "Migrate from Next.js",
                "to": "framework/react/migrate-from-next-js"
              }
            ]
          }
        ]
      }
    ]
  + .[1:]
)' docs/start/config.json >tmp && mv tmp docs/start/config.json
