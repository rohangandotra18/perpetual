# Persistent Context Sprint

Shared MongoDB cluster for this hackathon: **Cluster0** in the **SF .local Build Fest** sandbox.

This GitHub repo is **public**. The connection string stays in a local `.env` file, not in git.

## Setup

1. Copy the env file:

   ```bash
   cp .env.example .env
   ```

2. In Atlas, open the sandbox project → **Cluster0** → **Connect** → **Drivers**. Copy the `mongodb+srv://...` URI into `.env` as `MONGODB_URI`. Anyone invited to the sandbox project can copy this themselves.

3. In Atlas **Network Access**, allow `0.0.0.0/0` for the rest of the hackathon so teammates are not blocked by IP.

4. Install and verify:

   ```bash
   npm install
   npm run ping
   ```

App code should read `process.env.MONGODB_URI` (and `MONGODB_DB`). Never hardcode the URI.
