# Cloud Deployment Guide (take screenshots at every step for the report)

## Option A - Render.com (easiest, free, no credit card normally needed)
1. Create a free GitHub account and a new repository `lifelink`. Upload ALL project files
   (drag & drop in the GitHub web page is fine). Do NOT upload the `venv` folder or `.db` files.
2. Create a free account at https://render.com and click **New + -> Web Service**, connect GitHub, pick `lifelink`.
3. Settings: Runtime **Python 3**, Build command `pip install -r requirements.txt`,
   Start command `gunicorn app:app --workers 1 --threads 8`, Plan **Free**.
4. Under **Environment** add `SECRET_KEY` = any long random text (e.g. 40 random characters).
5. Click **Create Web Service**. After the build you get a public URL like `https://lifelink-xxxx.onrender.com`.
6. Open `<URL>/health` (should show `{"status":"ok"}`) and then the main page. Screenshot: Render dashboard (Events/Logs),
   the public URL working in the browser, and the Environment page (hide the secret value!).
Note: free Render instances sleep after inactivity (first load can take ~50 s) and the disk is temporary, so the demo
users are re-created on every restart. This is acceptable for the prototype and is discussed as a limitation in the report.

## Option B - Docker (local or any cloud VM)
```bash
docker build -t lifelink .
docker run -p 5000:5000 -e SECRET_KEY=change-this-long-random-value -v lifelink-data:/data lifelink
```
The named volume `lifelink-data` keeps the database across container restarts.

## Option C - AWS EC2 (Ubuntu t2.micro, free-tier)
1. Launch an Ubuntu 22.04 `t2.micro` instance. Security group: allow SSH (22) from your IP and Custom TCP **5000** from anywhere.
2. Connect via SSH, then:
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone https://github.com/<your-user>/lifelink.git && cd lifelink
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="long-random-value"
nohup gunicorn app:app --bind 0.0.0.0:5000 --workers 1 --threads 8 &
```
3. Open `http://<EC2-public-IP>:5000`. Screenshot: EC2 instance page, security group rules, app in browser. (Never show access keys.)
