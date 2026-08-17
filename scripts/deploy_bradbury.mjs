import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";


const __filename = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(__filename), "..");
const CONTRACT_PATH = path.join(ROOT, "contracts", "dependency_license_drift.py");
const EVIDENCE_DIR = path.join(ROOT, "docs", "evidence", "bradbury");
const DEPLOYMENT_PATH = path.join(EVIDENCE_DIR, "deployment.json");
const LIFECYCLE_PATH = path.join(EVIDENCE_DIR, "lifecycle.json");

export const BRADBURY = {
  network: "testnet-bradbury",
  rpcUrl: "https://rpc-bradbury.genlayer.com",
  chainId: "0x107d",
  chainIdDecimal: 4221,
  explorerBase: "https://explorer-bradbury.genlayer.com",
};

export function parseExecutionResult(receipt) {
  if (!receipt || typeof receipt !== "object") return "";
  if (typeof receipt.txExecutionResultName === "string") return receipt.txExecutionResultName;
  if (typeof receipt.executionResult === "string") return receipt.executionResult;
  const leaderReceipt = receipt.consensus_data?.leader_receipt;
  if (Array.isArray(leaderReceipt)) {
    for (const item of leaderReceipt) {
      if (typeof item?.execution_result === "string") return item.execution_result;
      if (typeof item?.txExecutionResultName === "string") return item.txExecutionResultName;
    }
  }
  return "";
}

export function parseContractAddress(receipt) {
  if (!receipt || typeof receipt !== "object") return "";
  if (typeof receipt.contractAddress === "string") return receipt.contractAddress;
  if (typeof receipt.contract_address === "string") return receipt.contract_address;
  const leaderReceipt = receipt.consensus_data?.leader_receipt;
  if (Array.isArray(leaderReceipt)) {
    for (const item of leaderReceipt) {
      if (typeof item?.contract_address === "string") return item.contract_address;
      if (typeof item?.contractAddress === "string") return item.contractAddress;
    }
  }
  return "";
}

export function parseTxHash(receipt) {
  if (!receipt || typeof receipt !== "object") return "";
  return receipt.txHash || receipt.transaction_hash || receipt.hash || receipt.tx_id || "";
}

export function sanitizeReceipt(receipt, options = {}) {
  const network = options.network || BRADBURY.network;
  const explorerBase = options.explorerBase || BRADBURY.explorerBase;
  const txHash = parseTxHash(receipt);
  const contractAddress = parseContractAddress(receipt);
  const safe = {
    network,
    executionResult: parseExecutionResult(receipt),
  };
  if (txHash) {
    safe.txHash = txHash;
    safe.explorerUrl = `${explorerBase}/transactions/${txHash}`;
  }
  if (contractAddress) safe.contractAddress = contractAddress;
  return safe;
}

function readEnvFile(filePath) {
  if (!existsSync(filePath)) return {};
  const out = {};
  const text = readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const index = trimmed.indexOf("=");
    if (index === -1) continue;
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

export function loadSafeEnv() {
  const parentEnv = readEnvFile(path.join(ROOT, "..", ".env"));
  const projectEnv = readEnvFile(path.join(ROOT, ".env"));
  const merged = { ...process.env, ...parentEnv, ...projectEnv };
  return {
    network: merged.GENLAYER_NETWORK || "",
    privateKeyPresent: Boolean(merged.GENLAYER_PRIVATE_KEY),
    env: merged,
  };
}

function requireBradburyConfig() {
  const config = loadSafeEnv();
  if (config.network !== BRADBURY.network) {
    throw new Error("GENLAYER_NETWORK must be testnet-bradbury");
  }
  if (!config.privateKeyPresent) {
    throw new Error("GENLAYER_PRIVATE_KEY is missing");
  }
  return config;
}

function sourceIdentity() {
  const source = readFileSync(CONTRACT_PATH, "utf8");
  const header = source.split(/\r?\n/).slice(0, 3).join("\n");
  let commit = "";
  try {
    commit = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    commit = "UNKNOWN";
  }
  return {
    commit,
    contractPath: "contracts/dependency_license_drift.py",
    sourceSha256: createHash("sha256").update(source).digest("hex"),
    headerSha256: createHash("sha256").update(header).digest("hex"),
  };
}

async function rpcChainId() {
  const response = await fetch(BRADBURY.rpcUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_chainId", params: [] }),
  });
  const data = await response.json();
  return data.result || "";
}

function parseJsonFromOutput(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed);
  } catch {
    const match = trimmed.match(/\{[\s\S]*\}/);
    if (!match) return {};
    try {
      return JSON.parse(match[0]);
    } catch {
      return {};
    }
  }
}

function runGenlayer(args, env) {
  return execFileSync("genlayer", args, {
    cwd: ROOT,
    env,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function ensureEvidenceDir() {
  mkdirSync(EVIDENCE_DIR, { recursive: true });
}

async function inspect() {
  const config = loadSafeEnv();
  const chainId = await rpcChainId();
  const result = {
    network: BRADBURY.network,
    configuredNetwork: config.network || "MISSING",
    networkOk: config.network === BRADBURY.network,
    privateKeyPresent: config.privateKeyPresent,
    rpcUrl: BRADBURY.rpcUrl,
    chainId,
    chainIdOk: chainId === BRADBURY.chainId,
    explorer: BRADBURY.explorerBase,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!result.networkOk) throw new Error("GENLAYER_NETWORK must be testnet-bradbury");
  if (!result.privateKeyPresent) throw new Error("GENLAYER_PRIVATE_KEY is missing");
  if (!result.chainIdOk) throw new Error("Bradbury chain id mismatch");
}

function deploy() {
  const config = requireBradburyConfig();
  ensureEvidenceDir();
  const output = runGenlayer(
    ["deploy", "--contract", CONTRACT_PATH, "--rpc", BRADBURY.rpcUrl],
    config.env,
  );
  const parsed = parseJsonFromOutput(output);
  const safe = {
    ...sanitizeReceipt(parsed, BRADBURY),
    ...sourceIdentity(),
    network: BRADBURY.network,
  };
  if (!safe.executionResult) {
    safe.executionResult = "UNKNOWN";
  }
  writeFileSync(DEPLOYMENT_PATH, JSON.stringify(safe, null, 2) + "\n");
  console.log(JSON.stringify(safe, null, 2));
}

function schema() {
  const config = requireBradburyConfig();
  if (!existsSync(DEPLOYMENT_PATH)) throw new Error("deployment.json is missing");
  const deployment = JSON.parse(readFileSync(DEPLOYMENT_PATH, "utf8"));
  if (!deployment.contractAddress) throw new Error("contractAddress is missing");
  const output = runGenlayer(
    ["schema", deployment.contractAddress, "--rpc", BRADBURY.rpcUrl],
    config.env,
  );
  console.log(output.trim());
}

function demo() {
  requireBradburyConfig();
  throw new Error("demo is intentionally manual until deploy receipt parsing is verified");
}

function verify() {
  if (!existsSync(DEPLOYMENT_PATH)) throw new Error("deployment.json is missing");
  const deployment = JSON.parse(readFileSync(DEPLOYMENT_PATH, "utf8"));
  const identity = sourceIdentity();
  if (deployment.network !== BRADBURY.network) throw new Error("network mismatch");
  if (deployment.sourceSha256 !== identity.sourceSha256) throw new Error("source hash mismatch");
  console.log(JSON.stringify({ ok: true, network: deployment.network, contractAddress: deployment.contractAddress || "" }, null, 2));
}

async function main() {
  const command = process.argv[2] || "inspect";
  if (command === "inspect") return inspect();
  if (command === "deploy") return deploy();
  if (command === "schema") return schema();
  if (command === "demo") return demo();
  if (command === "verify") return verify();
  throw new Error(`unknown command: ${command}`);
}

if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
