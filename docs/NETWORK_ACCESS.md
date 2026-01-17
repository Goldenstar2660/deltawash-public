# Network Access Configuration

## Issue Fixed
The dashboard was trying to connect to `localhost:8000` which doesn't work when accessing from another device on the network.

## Changes Made

### 1. Frontend Configuration (`.env`)
Created `/dashboard/frontend/.env` with:
```
VITE_API_BASE_URL=http://172.20.10.3:8000
```

### 2. Docker Compose Updates
Updated `dashboard/docker-compose.dashboard.yml`:
- Frontend now defaults to `http://172.20.10.3:8000` instead of `localhost:8000`
- Backend CORS now includes `http://172.20.10.3:5173` for network access

### 3. Access URLs

From your computer on the same network, access the dashboard at:
```
http://172.20.10.3:5173
```

The backend API is at:
```
http://172.20.10.3:8000
```

## Current Pi IP Address
```
172.20.10.3
```

## Troubleshooting

If the IP address changes (different network, DHCP reassignment):

1. Get new IP:
   ```bash
   hostname -I
   ```

2. Update `.env` file:
   ```bash
   echo "VITE_API_BASE_URL=http://NEW_IP:8000" > dashboard/frontend/.env
   ```

3. Restart containers:
   ```bash
   docker compose -f dashboard/docker-compose.dashboard.yml restart frontend backend
   ```

## Testing

1. Hard refresh your browser: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
2. Open browser console (F12) to check for errors
3. Network tab should show requests going to `172.20.10.3:8000` instead of `localhost:8000`



