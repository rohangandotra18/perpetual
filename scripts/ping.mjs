import { readFileSync } from "node:fs";
import { MongoClient } from "mongodb";

function loadEnv(path) {
  const env = {};
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    env[trimmed.slice(0, eq)] = trimmed.slice(eq + 1);
  }
  return env;
}

const env = loadEnv(new URL("../.env", import.meta.url));
const uri = env.MONGODB_URI;
const dbName = env.MONGODB_DB || "hackathon";

if (!uri || uri.includes("<password>") || uri.includes("<cluster-id>")) {
  console.error("Set MONGODB_URI in .env first (copy .env.example).");
  process.exit(1);
}

const client = new MongoClient(uri);
try {
  await client.connect();
  const db = client.db(dbName);
  await db.command({ ping: 1 });
  const collections = await db.listCollections().toArray();
  console.log(`Connected to ${dbName} (${collections.length} collections)`);
} finally {
  await client.close();
}
