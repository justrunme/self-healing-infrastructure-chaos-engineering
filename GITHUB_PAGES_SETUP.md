# 🚀 GitHub Pages Setup Guide

## 📋 Prerequisites

Before running the GitHub Pages workflow, you need to configure GitHub Pages in your repository settings.

## ⚙️ Repository Settings Configuration

### 1. Enable GitHub Pages

1. Go to your repository on GitHub
2. Click on **Settings** tab
3. Scroll down to **Pages** section in the left sidebar
4. Under **Source**, select **Deploy from a branch**
5. Choose **Branch**: `main`
6. Choose **Folder**: `/docs`
7. Click **Save**

### 2. Configure Pages Permissions

1. In the same **Pages** section
2. Under **Build and deployment**
3. Make sure **GitHub Actions** is selected as the source
4. This allows the workflow to deploy to Pages

### 3. Verify Configuration

After setup, you should see:
- **Your site is published at**: `https://justrunme.github.io/self-healing-infrastructure-chaos-engineering/`
- **Source**: Deploy from a branch
- **Branch**: main /docs

## 🔧 Workflow Configuration

The workflow is already configured to:
- Deploy from `/docs` folder
- Use GitHub Actions for deployment
- Automatically trigger on push to main branch

## 🚀 Manual Deployment

If you want to manually trigger a deployment:

1. Go to **Actions** tab
2. Select **🚀 Deploy to GitHub Pages** workflow
3. Click **Run workflow**
4. Choose branch (usually `main`)
5. Click **Run workflow**

## 📊 Monitoring Deployment

### Check Workflow Status
1. Go to **Actions** tab
2. Click on the latest workflow run
3. Monitor each job:
   - 📋 Validate Documentation
   - 🏗️ Build Documentation
   - 🚀 Deploy to GitHub Pages
   - ⚡ Performance Test
   - 🔒 Security Scan
   - 📋 Deployment Summary

### Check Site Status
1. Visit your site URL
2. Check if all pages load correctly
3. Verify navigation links work
4. Test responsive design

## 🔍 Troubleshooting

### Common Issues

**1. "Pages build failed"**
- Check if `/docs` folder exists
- Verify all required files are present
- Check workflow logs for specific errors

**2. "Concurrency deadlock"**
- This is now fixed by removing concurrency settings
- Workflow should run without conflicts

**3. "Site not accessible"**
- Wait 5-10 minutes after deployment
- Check if GitHub Pages is enabled in settings
- Verify the correct branch and folder are selected

**4. "Performance test failed"**
- This is expected if site is not yet deployed
- Tests will use fallback URL and continue

### Debug Steps

1. **Check Repository Settings**
   ```
   Settings → Pages → Source: Deploy from a branch
   Branch: main
   Folder: /docs
   ```

2. **Check Workflow Logs**
   ```
   Actions → 🚀 Deploy to GitHub Pages → Click on failed job
   ```

3. **Verify File Structure**
   ```
   /docs/
   ├── index.md
   ├── architecture.md
   ├── components.md
   ├── self-healing.md
   ├── chaos-engineering.md
   ├── ci-cd.md
   ├── screenshots.md
   ├── links.md
   └── images/
   ```

## 🎯 Expected Results

After successful setup and deployment:

✅ **Site URL**: `https://justrunme.github.io/self-healing-infrastructure-chaos-engineering/`

✅ **Available Pages**:
- Main page with project overview
- Architecture documentation
- Components guide
- Self-healing explanation
- Chaos engineering details
- CI/CD pipeline documentation
- Screenshots gallery
- External links and resources

✅ **Features**:
- Responsive design
- SEO optimized
- Fast loading
- Professional appearance
- Comprehensive documentation

## 🔄 Automatic Updates

Once configured, the site will automatically update:
- On every push to main branch
- When releases are published
- Manual workflow triggers

## 📞 Support

If you encounter issues:
1. Check this guide first
2. Review workflow logs in Actions tab
3. Verify repository settings
4. Check GitHub Pages documentation

---

**Note**: This setup guide is specific to the self-healing infrastructure project. Adjust URLs and paths for your specific repository. 