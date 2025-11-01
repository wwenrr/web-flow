# Web Flow - Docker Container với VNC UI

## Local Usage

### Quick Start
```bash
# Start container
./bin/up

# Stop container
./bin/down
```

Hoặc dùng docker compose trực tiếp:
```bash
docker compose up -d --build
docker compose down -v
```

## GitHub Actions Workflow

### Cách sử dụng:

1. **Truy cập Actions tab** trên GitHub repository
2. **Chọn workflow** "Start Docker Container"
3. **Click "Run workflow"** button
4. **Chọn duration** (1h, 3h, 5h, 8h, 12h)
5. **Click "Run workflow"**

Workflow sẽ:
- Build Docker image
- Start container với VNC UI
- Chạy trong thời gian đã chọn
- Tự động tắt sau khi hết thời gian

### Setup Secrets

Thêm secret `TAILSCALE_AUTH_KEY` vào GitHub repository:
- Settings → Secrets and variables → Actions
- New repository secret
- Name: `TAILSCALE_AUTH_KEY`
- Value: Your Tailscale auth key

## Truy cập Container

- **VNC Web**: http://localhost:6901 (hoặc URL công khai của runner)
- **VNC Client**: localhost:5901
- **SSH**: ssh root@localhost -p 2222 (password: 1415)

## Ports

- **8080**: Application port
- **2222**: SSH port  
- **5901**: VNC port
- **6901**: noVNC Web port