# CHALDEAS Port Configuration

## Fixed Ports (Do Not Change)

| Service | Port | Description |
|---------|------|-------------|
| **Backend API** | 8100 | FastAPI REST API |
| **Frontend** | 5100 | React Vite Dev Server |
| **PostgreSQL** | 5433 | Database (if used) |

## Why These Ports

- `8100`: Unique backend port (avoids 8000, 8080 common conflicts)
- `5100`: Unique frontend port (avoids 5173, 3000 common conflicts)
- `5433`: Unique DB port (avoids 5432 default PostgreSQL)

## Environment Variables

```bash
# .env file
BACKEND_PORT=8100
FRONTEND_PORT=5100
DATABASE_PORT=5433
VITE_API_URL=http://localhost:8100
```

## Docker Compose Ports

```yaml
services:
  db:
    ports:
      - "5433:5432"
  backend:
    ports:
      - "8100:8000"
  frontend:
    ports:
      - "5100:5173"
```
