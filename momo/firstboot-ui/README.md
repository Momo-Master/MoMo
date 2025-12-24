# MoMo First Boot Wizard UI

React-based setup wizard for MoMo first boot experience.

## Features

- 📱 **Mobile-First Design** - Optimized for phone/tablet access
- 🌐 **Multi-Language** - English and Turkish support
- 🔐 **Password Setup** - With strength indicator
- 📡 **Network Configuration** - AP or Client mode
- 🎯 **Profile Selection** - Passive, Balanced, Aggressive
- 🔗 **Nexus Integration** - mDNS discovery + manual entry
- ✅ **Summary & Confirmation** - Review before completing

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production (outputs to ../firstboot/static/)
npm run build
```

## Stack

- React 19
- TypeScript
- Tailwind CSS
- Vite
- Lucide Icons

## Wizard Flow

```
Welcome → Password → Network → Profile → Nexus → Summary → Complete
   ↓          ↓          ↓          ↓         ↓         ↓
Language  Admin PWD   AP/Client  Operation  Optional  Review
```

## API Endpoints

The wizard communicates with the FastAPI backend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get wizard state |
| `/api/step/language` | POST | Set language |
| `/api/step/password` | POST | Set admin password |
| `/api/wifi/scan` | GET | Scan WiFi networks |
| `/api/step/network` | POST | Configure network |
| `/api/step/profile` | POST | Set operation profile |
| `/api/nexus/discover` | GET | mDNS Nexus discovery |
| `/api/step/nexus` | POST | Configure Nexus |
| `/api/complete` | POST | Finish setup |

## Building for Pi

```bash
npm run build
# Output goes to ../firstboot/static/
# This is served by the FastAPI wizard server
```

