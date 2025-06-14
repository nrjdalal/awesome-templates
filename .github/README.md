# Awesome Templates

[![Twitter](https://img.shields.io/twitter/follow/nrjdalal_com?label=%40nrjdalal_com)](https://twitter.com/nrjdalal_com) [![Awesome](https://awesome.re/badge.svg)](https://github.com/nrjdalal/awesome-templates) [![GitHub](https://img.shields.io/github/stars/nrjdalal/awesome-templates?color=blue)](https://github.com/nrjdalal/awesome-templates)

> 🟤 Last updated: Jun 14 08:09 UTC 25

Explore a curated collection of up-to-date templates for various projects and frameworks, refreshed every 8 hours.

> [!NOTE]
> If there are no changes to a template, the last updated timestamp will not change for that template.

## Why?

Deep into a project and need to refer back to the initial or starter version? 😩

Tired of repeatedly setting up and deleting test directories for various projects? It's a mess. 😭

Here's your solution: reference templates, updated every hour to ensure they're the latest and greatest. 🚀

## Clone a Template

Easily clone a template using [gitpick](https://github.com/nrjdalal/gitpick) with the following command:

```bash
npx gitpick@latest nrjdalal/awesome-templates/tree/main/<template-folder>/<template-name>
```

The command to clone a template also exists at the `README.md` of each template.

## Contributing

We welcome contributions from the community! To contribute to this project, please follow these steps:

1. **Fork the repository on GitHub.**

2. **Create a new branch**

```bash
git checkout -b react-template
```

3. **Add your new script in the `.github/.scripts/` directory.** For example, `.github/.scripts/react.sh`.

&nbsp;&nbsp;&nbsp;&nbsp;----- ./github/.scripts/react.sh -----
<br/>
&nbsp;&nbsp;&nbsp;&nbsp;bunx create-react-app awesomedir<br/>
&nbsp;&nbsp;&nbsp;&nbsp;cd awesomedir<br/>
&nbsp;&nbsp;&nbsp;&nbsp;rm -rf README.md
<br/>
&nbsp;&nbsp;&nbsp;&nbsp;------------------------------------

> [!IMPORTANT]
> In the script, use `awesomedir` as the target directory for the template. If you need to run some further commands, then make sure to `cd` into the target directory first.

> [!NOTE]
> The script's name without the `.sh` extension will be used as the template directory.

4. Try to test locally if you can, using [act](https://github.com/nektos/act) medium/large image and the following command:

```bash
act
```

This process will execute only for the modified script, ensuring efficient testing and validation.

> [!NOTE]
> If you mistakenly chose the wrong image, check out this [issue](https://github.com/nektos/act/issues/2219) for solution.

5. **Make your changes and commit them with a clear and descriptive commit message.**

```bash
git commit -am 'added new template for react'
```

6. **Push your branch to your forked repository.**

```bash
git push origin react-template
```

7. **Open a pull request on the original repository and provide a detailed description of your changes.**
