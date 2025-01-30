# Awesome Templates

> 🔵 Last updated: Jan 30 08:02 UTC 25

Explore a curated collection of up-to-date templates for various projects and frameworks, refreshed every 8 hours.

> [!NOTE]
> If there are no changes to a template, the last updated timestamp will not change for that template.

## Why?

Deep into a project and need to refer back to the initial or starter version? 😩

Tired of repeatedly setting up and deleting test directories for various projects? It's a mess. 😭

Here's your solution: reference templates, updated every 8 hours to ensure they're the latest and greatest. 🚀

## Clone a Template

To clone a template, run the following command:

```bash
npx gitpick clone nrjdalal/awesome-templates "<template-folder>/<template-name>" "<target-directory>"
```

## Contributing

We welcome contributions from the community! To contribute to this project, please follow these steps:

1. **Fork the repository on GitHub.**

2. **Create a new branch from `main` for your new template.**

```bash
git checkout -b react-template
```

3. **Add your new script in the `./.scripts/` directory.** For example, `./.scripts/react.sh`.

> [!NOTE]
> The script's name without the `.sh` extension will be used as the template directory.

> [!IMPORTANT]
> In the script, use `awesomedir` as the target directory for the template.

```bash
bunx creat-react-app awesomedir
```

4. **Make your changes and commit them with a clear and descriptive commit message.**

```bash
git commit -am 'added new template for react'
```

5. **Push your branch to your forked repository.**

```bash
git push origin react-template
```

6. **Open a pull request on the original repository and provide a detailed description of your changes.**
