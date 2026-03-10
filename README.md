# USPhoneBook Scraper

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-private-red.svg)]()

Dockerized scraper for [USPhoneBook.com](https://www.usphonebook.com/) with automatic
Cloudflare Turnstile bypass. Runs headless Chrome behind Xvfb virtual display to avoid
headless-detection while requiring zero GUI on the host.

---

## Architecture

```
Host (any Linux server)
 |
 +-- Docker container
      |-- Xvfb :99           Virtual X11 display (1920x1080)
      |-- Google Chrome       Launched via nodriver (undetected)
      |-- scraper.py          Main orchestration script
      |-- nodriver_cf_verify  Cloudflare Turnstile solver
      +-- SOCKS5 proxy        US IP required by USPhoneBook
```

**Data flow:**

1. Browser opens `usphonebook.com` through a US SOCKS5 proxy
2. Cloudflare Turnstile challenge is detected and solved automatically
3. Phone number search page is loaded
4. HTML is parsed with regex to extract structured data
5. Results (JSON + screenshot + debug HTML) are saved to `results/`

## Quick Start

```bash
# Clone the repository
git clone https://github.com/mazamaka/usphonebook-scraper.git
cd usphonebook-scraper

# Create .env file with your proxy
echo 'PROXY_URL=socks5://user:pass@proxy.example.com:1080' > .env

# Build the Docker image
docker compose build

# Run a phone lookup
docker compose run --rm scraper 828-685-1514
```

Results will appear in the `results/` directory.

## Configuration

### Environment Variables

| Variable    | Required | Description                          |
|-------------|----------|--------------------------------------|
| `PROXY_URL` | Yes      | SOCKS5 proxy URL with US IP address  |
| `DISPLAY`   | No       | X11 display (default `:99`, set by entrypoint) |

### Proxy Setup

The scraper **requires a US IP address** -- USPhoneBook blocks non-US traffic.

Set `PROXY_URL` in your environment or `.env` file:

```bash
# Static proxy
PROXY_URL=socks5://user:pass@proxy.example.com:1080

# Rotating proxy with session template (SOAX-style)
PROXY_URL=socks5://user-sessionid-{session}:pass@proxy.example.com:1080
```

When `{session}` is present in the URL, the scraper generates a random session ID
on each run to get a fresh IP from the proxy pool.

### Docker Compose Override

To customize resource limits or add your `.env` file:

```yaml
# docker-compose.override.yml
services:
  scraper:
    env_file: .env
    shm_size: '2gb'
```

## Output

Results are saved to `results/` with the phone number as filename prefix:

| File                          | Description              |
|-------------------------------|--------------------------|
| `result_XXXXXXXXXX.json`      | Extracted structured data |
| `result_XXXXXXXXXX.png`       | Page screenshot          |
| `debug_XXXXXXXXXX.html`       | Raw HTML for debugging   |

### Example JSON Output

```json
{
  "full_name": "Angela Murray",
  "phones": ["828-685-1514"],
  "addresses": [
    "22 Treemont Ln, Hendersonville, NC 28792",
    "26 Stepp Mill Rd, Hendersonville, NC 28792"
  ],
  "relatives": [
    "Bobby Hylemon",
    "Diane Patterson",
    "Lillian Hawkins"
  ],
  "status": "success"
}
```

## Project Structure

```
.
├── Dockerfile              Docker image (Chrome + Xvfb + Python)
├── docker-compose.yml      Container orchestration
├── scraper.py              Main scraper script
├── nodriver_cf_verify/     Cloudflare Turnstile bypass module (AGPL-3.0)
│   ├── __init__.py
│   └── cf_verify.py
├── requirements.txt        Python dependencies
└── results/                Output directory (git-ignored)
    └── .gitkeep
```

## Tech Stack

| Component              | Purpose                                      |
|------------------------|----------------------------------------------|
| **nodriver**           | Chrome automation without detection           |
| **nodriver-cf-verify** | Automatic Cloudflare Turnstile solver         |
| **Xvfb**              | Virtual display (bypasses headless detection) |
| **loguru**             | Structured logging                           |
| **httpx**              | HTTP client                                  |
| **pydantic**           | Data validation                              |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Timeout on main page | Proxy not working or not US | Check proxy connectivity and geolocation |
| Cloudflare not passing | Turnstile update broke solver | Check `nodriver_cf_verify` for updates |
| Empty results | Page structure changed | Inspect `debug_*.html` and update regex patterns |
| Chrome crash | Insufficient shared memory | Increase `shm_size` in docker-compose.yml |

## Requirements

- Docker + Docker Compose
- US SOCKS5 proxy (the service blocks non-US IPs)
- ~2 GB RAM per container (Chrome + Xvfb)

## License

Private / Internal Use Only.

The `nodriver_cf_verify` module is licensed under [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) by OMEGASTRUX.
