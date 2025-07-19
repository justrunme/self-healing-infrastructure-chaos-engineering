# 🔧 Setup GitHub Pages

!!! warning "📋 GitHub Pages Configuration Required"
    To see the beautiful MkDocs site instead of raw markdown, you need to configure GitHub Pages settings.

## 🎯 Current Issue

Currently, GitHub Pages is showing raw markdown files instead of the compiled MkDocs site. This results in:

- ❌ Raw markdown text instead of styled content
- ❌ Badges showing as code instead of images
- ❌ No Material Design theme
- ❌ No navigation or search functionality

## ✅ Solution: Configure GitHub Actions Deployment

### Step 1: Access Repository Settings

1. Go to your repository: [self-healing-infrastructure-chaos-engineering](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering)
2. Click on **Settings** tab
3. Scroll down to **Pages** in the left sidebar

### Step 2: Change Source Configuration

**Current Setting:**
```
Source: Deploy from a branch
Branch: main
Folder: /docs
```

**Change To:**
```
Source: GitHub Actions
```

### Step 3: Verify Deployment

After changing the source:

1. Go to [Actions tab](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions)
2. Wait for the "Deploy MkDocs site to GitHub Pages" workflow to complete
3. Your site will be available at: [https://justrunme.github.io/self-healing-infrastructure-chaos-engineering/](https://justrunme.github.io/self-healing-infrastructure-chaos-engineering/)

## 🎨 What You'll Get

After proper configuration, your site will have:

- ✅ Beautiful Material Design theme
- ✅ Dark/light mode toggle
- ✅ Navigation tabs and sections
- ✅ Search functionality
- ✅ Proper badge rendering
- ✅ Code syntax highlighting
- ✅ Responsive design

## 🚀 Auto-Deployment

Once configured, the site will automatically update whenever you push to the main branch:

1. **Push to main** → GitHub Actions trigger
2. **MkDocs build** → Site compilation
3. **Deploy to Pages** → Live site update
4. **Available in ~5 minutes** ⚡

## 📞 Need Help?

If you see raw markdown instead of the styled site, check:

1. GitHub Pages source is set to "GitHub Actions"
2. Latest workflow completed successfully
3. Allow 5-10 minutes for deployment

---

**🎉 Once configured, delete this file and enjoy your beautiful documentation site!** 