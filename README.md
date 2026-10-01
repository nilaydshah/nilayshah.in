# nilayshah.in

Personal website for Nilay Shah, built with Hugo and PaperMod and deployed through Azure Static Web Apps.

## Local development

Initialize the theme submodule after cloning:

```powershell
git submodule update --init --recursive
```

Run the local site:

```powershell
hugo server
```

Create the production output:

```powershell
hugo --minify --gc
```
