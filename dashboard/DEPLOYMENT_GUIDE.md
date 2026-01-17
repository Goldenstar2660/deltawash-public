# Deployment Guide: Handwash Dashboard

This guide will help you deploy your dashboard with:
- **Frontend** -> Static hosting provider of your choice
- **Backend** -> Render (free tier) with PostgreSQL database

---

## 📋 Prerequisites

- A GitHub account (to connect your code)
- Your .tech domain ready
- About 30 minutes of time

---

## Part 1: Deploy Backend to Render (15 min)

Render offers a free tier perfect for small projects.

### Step 1: Create Render Account

1. Go to [render.com](https://render.com)
2. Click **"Get Started for Free"**
3. Select **"GitHub"** to sign up with your GitHub account
4. Authorize Render to access your GitHub

### Step 2: Create PostgreSQL Database First

1. From the Render dashboard, click **"New +"** button
2. Select **"PostgreSQL"**
3. Fill in the details:
   - **Name**: `handwash-db`
   - **Database**: `handwash`
   - **User**: Leave as default
   - **Region**: Choose closest to you (e.g., Oregon for US West)
   - **PostgreSQL Version**: 15
   - **Instance Type**: Select **"Free"**
4. Click **"Create Database"**
5. Wait for it to be created (1-2 minutes)
6. Once ready, find the **"Internal Database URL"** - you'll need this later (it starts with `postgres://`)

### Step 3: Create the Backend Web Service

1. Click **"New +"** → **"Web Service"**
2. Select **"Build and deploy from a Git repository"** → **"Next"**
3. Connect your GitHub repo:
   - Find and click **"Connect"** next to `DeltaWash` (or your repo name)
4. Configure the service:

| Setting | Value |
|---------|-------|
| **Name** | `handwash-api` |
| **Region** | Same as your database |
| **Branch** | `clean-main` (or your main branch) |
| **Root Directory** | `dashboard/backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | **Free** |

### Step 4: Add Environment Variables

1. Scroll down to **"Environment Variables"**
2. Click **"Add Environment Variable"** for each:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Paste the **Internal Database URL** from Step 2 |
| `JWT_SECRET` | Generate with: `openssl rand -hex 32` in your terminal |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` |
| `CORS_ORIGINS` | `https://yourdomain.tech,https://www.yourdomain.tech` |
| `PYTHON_VERSION` | `3.11.7` |

### Step 5: Deploy

1. Click **"Create Web Service"**
2. Render will start building and deploying (3-5 minutes)
3. Watch the logs - it should say "Uvicorn running on..."
4. Your backend URL appears at the top (e.g., `https://handwash-api.onrender.com`)
5. **Copy this URL!** You'll need it for the frontend

### Step 6: Seed Demo Data (Optional)

If you want demo data in your dashboard:
1. Go to your web service on Render
2. Click **"Shell"** tab (or use the "Manual Deploy" → Run in shell)
3. Run: `python -m src.scripts.seed_demo_data`
4. This adds sample data to test with

### ⚠️ Important Note About Free Tier

Render's free tier spins down after 15 minutes of inactivity. First request after sleep takes ~30 seconds. This is normal for free tier!

---

## Part 2: Deploy Frontend (provider-specific)

This project uses a Vite frontend located in `dashboard/frontend`.

### Step 1: Build the frontend

1. From `dashboard/frontend`, run:
   - `npm install`
   - `npm run build`
2. The build output is in `dist/`.

### Step 2: Configure environment variables in your host

Set `VITE_API_BASE_URL` to your backend URL from Part 1.

### Step 3: Deploy

Upload the `dist/` folder or connect your repo with these settings:
- **Root Directory**: `dashboard/frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

---

## Part 3: Connect Your Domain (provider-specific)

1. Add your domain in your frontend hosting provider's settings.
2. Update DNS at your registrar using the records your provider supplies.
3. Wait for DNS propagation, then verify HTTPS is enabled.

---

## Part 4: Update Backend CORS (Important!)

After you have your domain set up, update the backend to accept requests from it:

1. Go to Render → Your web service → **"Environment"** tab
2. Update `CORS_ORIGINS` to include your new domain:
   ```
   https://yourdomain.tech,https://www.yourdomain.tech
   ```
3. Click **"Save Changes"** - Render will automatically redeploy

---

## ✅ Final Checklist

- [ ] Backend deployed on Render
- [ ] PostgreSQL database connected
- [ ] Frontend deployed
- [ ] .tech domain connected
- [ ] HTTPS working (green lock icon)
- [ ] CORS configured correctly
- [ ] Demo data seeded (optional)

---

## 🧪 Test Your Deployment

1. Visit `https://yourdomain.tech`
2. The dashboard should load
3. Check browser console (F12) for any errors
4. Test navigation between pages

---

## 🔧 Troubleshooting

### "Failed to fetch" or CORS errors
- Check that `CORS_ORIGINS` in Render includes your exact domain with `https://`
- Make sure `VITE_API_BASE_URL` in your frontend host doesn't have a trailing slash

### Backend not starting
- Check Render logs: Click on service → **"Logs"** tab
- Make sure all environment variables are set correctly
- Verify DATABASE_URL is the **Internal** Database URL

### First load is slow
- Render free tier sleeps after 15 min of inactivity
- First request wakes it up (~30 seconds)
- This is normal for free tier!

### Domain not working
- DNS can take up to 48 hours (usually 10-30 mins)
- Verify DNS with: `nslookup yourdomain.tech`

### Database connection errors
- Use **Internal Database URL** (not External) for the backend
- Check PostgreSQL is running in Render dashboard

---

## 💰 Cost Summary

| Service | Cost |
|---------|------|
| Frontend hosting | Depends on provider |
| Render Backend | **Free** (750 hours/month) |
| Render PostgreSQL | **Free** (90 days, then $7/month) |
| .tech Domain | Whatever you paid |
| **Total Monthly** | **$0** (within free tier limits) |

---

## 🔄 Future Updates

When you push code to GitHub:
- **Frontend**: your host may auto-deploy on every push (if connected)
- **Backend**: Render auto-deploys on every push

No manual action needed!

---

## 📞 Need Help?

- Render Docs: https://render.com/docs
- Check the logs in each platform for error details
