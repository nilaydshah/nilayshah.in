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
python scripts/fetch_substack_feed.py --allow-stale
hugo --minify --gc
```

The deployment workflow refreshes the public Substack feed before every build and
runs daily so new posts appear in the **Latest from The AI-Native Engineer**
section without a website content change.
