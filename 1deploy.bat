@echo off
cd /d "D:\Desktop\quartz"

echo [1/3] Adding changes...
git add .

echo [2/3] Committing changes...
git commit -m "Auto update blog"

echo [3/3] Pushing to GitHub...
git push origin main --force

echo.
echo ====================================
echo  Success! Cloudflare is building.
echo ====================================
timeout /t 3