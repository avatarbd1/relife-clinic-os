#!/data/data/com.termux/files/usr/bin/bash

echo "Saving project..."

git add .

git commit -m "Auto Save: $(date '+%Y-%m-%d %H:%M')"

git push origin main

echo "✅ Project saved to GitHub!"
