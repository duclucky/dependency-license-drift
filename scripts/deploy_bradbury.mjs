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
const PRIVATE_KEY_NAMES = ["GENLAYER_PRIVATE_KEY", "STUDIONET_PRIVATE_KEY", "PRIVATE_KEY"];
const CHALLENGER_KEY_NAMES = [
  "GENLAYER_CHALLENGER_PRIVATE_KEY",
  "STUDIONET_INTEGRATOR_PRIVATE_KEY",
  "STUDIONET_CHALLENGER_PRIVATE_KEY",
  "STUDIONET_PRIVATE_KEY",
];
const GEN = 10n ** 18n;

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

export function parseTextReceiptFields(text) {
  const body = String(text || "");
  const txMatch =
    body.match(/Deployment Transaction Hash:\s*(0x[a-fA-F0-9]+)/) ||
    body.match(/Transaction Hash:\s*(0x[a-fA-F0-9]+)/);
  const addressMatch =
    body.match(/Contract Address:\s*(0x[a-fA-F0-9]{40})/) ||
    body.match(/contract_address['"]?\s*:\s*['"]?(0x[a-fA-F0-9]{40})/);
  const out = {};
  if (txMatch) out.txHash = txMatch[1];
  if (addressMatch) out.contractAddress = addressMatch[1];
  return out;
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
  let privateKey = "";
  for (const name of PRIVATE_KEY_NAMES) {
    if (merged[name]) {
      privateKey = merged[name];
      break;
    }
  }
  const effectiveNetwork = merged.GENLAYER_NETWORK || BRADBURY.network;
  return {
    network: effectiveNetwork,
    privateKeyPresent: Boolean(privateKey),
    env: { ...merged, GENLAYER_NETWORK: BRADBURY.network, GENLAYER_PRIVATE_KEY: privateKey },
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

function readPrivateKey(env, names) {
  for (const name of names) {
    const value = String(env[name] || "").trim();
    if (!value) continue;
    if (!/^(0x)?[0-9a-fA-F]{64}$/.test(value)) {
      throw new Error(`${name} is present but not a 32-byte hex key`);
    }
    return value.startsWith("0x") ? value : `0x${value}`;
  }
  throw new Error(`${names.join(" or ")} missing`);
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
  let command = "genlayer";
  let finalArgs = args;
  if (process.platform === "win32") {
    for (const dir of String(process.env.PATH || "").split(path.delimiter)) {
      const shim = path.join(dir, "genlayer.cmd");
      const script = path.join(dir, "node_modules", "genlayer", "dist", "index.js");
      const nodeExe = path.join(dir, "node.exe");
      if (existsSync(shim) && existsSync(script) && existsSync(nodeExe)) {
        command = nodeExe;
        finalArgs = [script, ...args];
        break;
      }
    }
  }
  return execFileSync(command, finalArgs, {
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
  const parsed = { ...parseJsonFromOutput(output), ...parseTextReceiptFields(output) };
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

function receiptSummary(hash, receipt) {
  return {
    txHash: hash,
    status: String(receipt?.status_name || receipt?.statusName || receipt?.status || ""),
    resultName: String(receipt?.resultName || receipt?.result_name || receipt?.txResultName || ""),
    executionResult: String(
      receipt?.txExecutionResultName || receipt?.executionResult || receipt?.execution_result || "",
    ),
  };
}

async function waitAccepted(client, hash) {
  return client.waitForTransactionReceipt({
    hash,
    status: "ACCEPTED",
    interval: 5000,
    retries: 120,
    fullTransaction: true,
  });
}

function safeErrorMessage(error) {
  const message = String(error?.message || error || "");
  if (message.includes("rate limit") || message.includes("node is at capacity")) {
    return "Bradbury RPC rate limited: node is at capacity";
  }
  if (message.includes("insufficient funds")) {
    return "account has insufficient funds";
  }
  if (message.includes("execution reverted") || message.includes("revert")) {
    return "transaction reverted";
  }
  return message.slice(0, 180) || "unknown error";
}

function writeLifecycle(lifecycle) {
  ensureEvidenceDir();
  writeFileSync(LIFECYCLE_PATH, JSON.stringify(lifecycle, null, 2) + "\n");
}

async function writeAccepted(client, address, functionName, args, value = 0n, options = {}) {
  let hash = "";
  let lastError = null;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      hash = await client.writeContract({ address, functionName, args, value });
      if (typeof options.onSubmitted === "function") {
        options.onSubmitted(hash);
      }
      break;
    } catch (error) {
      lastError = error;
      const message = String(error?.message || error);
      if (!message.includes("rate limit") && !message.includes("node is at capacity")) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500 + attempt * 1500));
    }
  }
  if (!hash) throw lastError || new Error(`${functionName} did not submit`);
  const receipt = await waitAccepted(client, hash);
  return receiptSummary(hash, receipt);
}

async function readView(client, address, functionName, args = []) {
  return client.readContract({ address, functionName, args, jsonSafeReturn: true });
}

async function demo() {
  const config = requireBradburyConfig();
  if (!existsSync(DEPLOYMENT_PATH)) throw new Error("deployment.json is missing");
  const deployment = JSON.parse(readFileSync(DEPLOYMENT_PATH, "utf8"));
  if (!deployment.contractAddress) throw new Error("contractAddress is missing");
  const { createAccount, createClient } = await import("genlayer-js");
  const { testnetBradbury } = await import("genlayer-js/chains");
  const sponsor = createAccount(readPrivateKey(config.env, PRIVATE_KEY_NAMES));
  const challenger = createAccount(readPrivateKey(config.env, CHALLENGER_KEY_NAMES));
  const sponsorClient = createClient({
    chain: testnetBradbury,
    endpoint: BRADBURY.rpcUrl,
    account: sponsor,
  });
  const challengerClient = createClient({
    chain: testnetBradbury,
    endpoint: BRADBURY.rpcUrl,
    account: challenger,
  });
  const reader = createClient({ chain: testnetBradbury, endpoint: BRADBURY.rpcUrl });
  const chainId = await reader.request({ method: "eth_chainId", params: [] });
  if (chainId !== BRADBURY.chainId) throw new Error("Bradbury chain id mismatch");

  const suffix = Date.now().toString(36);
  const covenantId = `dld-${suffix}`;
  const caseId = `case-${suffix}`;
  const lifecycle = {
    network: BRADBURY.network,
    status: "IN_PROGRESS",
    contractAddress: deployment.contractAddress,
    covenantId,
    caseId,
    sponsor: sponsor.address,
    challenger: challenger.address,
    txs: {},
    canonicalReads: {},
    evidenceIsSanitized: true,
  };
  writeLifecycle(lifecycle);
  try {
    lifecycle.txs.activate = await writeAccepted(
      sponsorClient,
      deployment.contractAddress,
      "activate_covenant",
      [
        covenantId,
        "ua-parser-js",
        "1.0.37",
        "Commercial SaaS may not accept AGPL or network-copyleft obligations.",
        4102444800,
      ],
      2n * GEN,
      {
        onSubmitted(hash) {
          lifecycle.txs.activate = { txHash: hash, status: "SUBMITTED" };
          writeLifecycle(lifecycle);
        },
      },
    );
    writeLifecycle(lifecycle);
    lifecycle.txs.openCase = await writeAccepted(
      challengerClient,
      deployment.contractAddress,
      "open_case",
      [covenantId, caseId, "2.0.0"],
      1n * GEN,
      {
        onSubmitted(hash) {
          lifecycle.txs.openCase = { txHash: hash, status: "SUBMITTED" };
          writeLifecycle(lifecycle);
        },
      },
    );
    writeLifecycle(lifecycle);
    lifecycle.txs.adjudicate = await writeAccepted(
      sponsorClient,
      deployment.contractAddress,
      "adjudicate_case",
      [caseId],
      0n,
      {
        onSubmitted(hash) {
          lifecycle.txs.adjudicate = { txHash: hash, status: "SUBMITTED" };
          writeLifecycle(lifecycle);
        },
      },
    );
    writeLifecycle(lifecycle);
  } catch (error) {
    lifecycle.status = "FAILED_PARTIAL";
    lifecycle.safeError = safeErrorMessage(error);
    writeLifecycle(lifecycle);
    throw error;
  }
  const statusAfterAdjudication = await readView(
    reader,
    deployment.contractAddress,
    "get_package_status",
    [covenantId],
  );
  const verdict = await readView(reader, deployment.contractAddress, "get_verdict", [caseId]);
  const challengerCredit = await readView(
    reader,
    deployment.contractAddress,
    "get_credit",
    [challenger.address],
  );
  lifecycle.txs.withdraw = await writeAccepted(
    challengerClient,
    deployment.contractAddress,
    "withdraw_credit",
    [],
    0n,
    {
      onSubmitted(hash) {
        lifecycle.txs.withdraw = { txHash: hash, status: "SUBMITTED" };
        writeLifecycle(lifecycle);
      },
    },
  );
  const accounting = await readView(reader, deployment.contractAddress, "get_accounting", []);
  lifecycle.status = "ACCEPTED_NOT_FINALIZED";
  lifecycle.canonicalReads = {
    statusAfterAdjudication,
    verdict,
    challengerCreditBeforeWithdraw: challengerCredit,
    accountingAfterWithdraw: accounting,
  };
  writeLifecycle(lifecycle);
  console.log(JSON.stringify(lifecycle, null, 2));
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
