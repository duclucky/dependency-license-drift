import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";


const __filename = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(__filename), "..");
const CONTRACT_PATH = path.join(ROOT, "contracts", "dependency_license_drift.py");
const EVIDENCE_DIR = path.join(ROOT, "docs", "evidence", "studionet");
const DEPLOYMENT_PATH = path.join(EVIDENCE_DIR, "deployment.json");
const DRIFT_PAYOUT_PATH = path.join(EVIDENCE_DIR, "drift-payout.json");
const RECOVERY_PATH = path.join(EVIDENCE_DIR, "recovery.json");
const PRIVATE_KEY_NAMES = ["GENLAYER_PRIVATE_KEY", "STUDIONET_PRIVATE_KEY", "PRIVATE_KEY"];
const CHALLENGER_KEY_NAMES = [
  "GENLAYER_CHALLENGER_PRIVATE_KEY",
  "STUDIONET_INTEGRATOR_PRIVATE_KEY",
  "STUDIONET_CHALLENGER_PRIVATE_KEY",
  "STUDIONET_PRIVATE_KEY",
];
const GEN = 10n ** 18n;

export const STUDIONET = {
  network: "studionet",
  rpcUrl: "https://studio.genlayer.com/api",
  chainId: "0xf22f",
  chainIdDecimal: 61999,
  explorerBase: "https://explorer-studio.genlayer.com",
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

export function isTransientStudionetError(error) {
  const message = String(error?.message || error || "");
  return (
    message.includes("rate limit") ||
    message.includes("node is at capacity") ||
    message.includes("transaction gas rate limit exceeded")
  );
}

export function isAcceptedExplorerStatus(status) {
  const value = String(status || "").toLowerCase();
  return value === "accepted" || value === "finalized";
}

export function sanitizeReceipt(receipt, options = {}) {
  const network = options.network || STUDIONET.network;
  const explorerBase = options.explorerBase || STUDIONET.explorerBase;
  const txHash = parseTxHash(receipt);
  const contractAddress = parseContractAddress(receipt);
  const safe = {
    network,
    executionResult: parseExecutionResult(receipt),
  };
  if (txHash) {
    safe.txHash = txHash;
    safe.explorerUrl = `${explorerBase}/tx/${txHash}`;
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
  const effectiveNetwork = merged.GENLAYER_NETWORK || STUDIONET.network;
  return {
    network: effectiveNetwork,
    privateKeyPresent: Boolean(privateKey),
    env: { ...merged, GENLAYER_NETWORK: STUDIONET.network, GENLAYER_PRIVATE_KEY: privateKey },
  };
}

function requireStudionetConfig() {
  const config = loadSafeEnv();
  if (config.network !== STUDIONET.network) {
    throw new Error("GENLAYER_NETWORK must be studionet");
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
  const response = await fetch(STUDIONET.rpcUrl, {
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

function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function inspect() {
  const config = loadSafeEnv();
  const chainId = await rpcChainId();
  const result = {
    network: STUDIONET.network,
    configuredNetwork: config.network || "MISSING",
    networkOk: config.network === STUDIONET.network,
    privateKeyPresent: config.privateKeyPresent,
    rpcUrl: STUDIONET.rpcUrl,
    chainId,
    chainIdOk: chainId === STUDIONET.chainId,
    explorer: STUDIONET.explorerBase,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!result.networkOk) throw new Error("GENLAYER_NETWORK must be studionet");
  if (!result.privateKeyPresent) throw new Error("GENLAYER_PRIVATE_KEY is missing");
  if (!result.chainIdOk) throw new Error("studionet chain id mismatch");
}

function deploy() {
  const config = requireStudionetConfig();
  ensureEvidenceDir();
  let output = "";
  let lastError = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      output = runGenlayer(
        ["deploy", "--contract", CONTRACT_PATH, "--rpc", STUDIONET.rpcUrl],
        config.env,
      );
      break;
    } catch (error) {
      lastError = error;
      if (!isTransientStudionetError(error)) throw error;
      sleepSync(1000 + attempt * 1500);
    }
  }
  if (!output) throw lastError || new Error("deploy did not return output");
  const parsed = { ...parseJsonFromOutput(output), ...parseTextReceiptFields(output) };
  const safe = {
    ...sanitizeReceipt(parsed, STUDIONET),
    ...sourceIdentity(),
    network: STUDIONET.network,
  };
  if (!safe.executionResult) {
    safe.executionResult = "UNKNOWN";
  }
  writeFileSync(DEPLOYMENT_PATH, JSON.stringify(safe, null, 2) + "\n");
  console.log(JSON.stringify(safe, null, 2));
}

function schema() {
  const config = requireStudionetConfig();
  if (!existsSync(DEPLOYMENT_PATH)) throw new Error("deployment.json is missing");
  const deployment = JSON.parse(readFileSync(DEPLOYMENT_PATH, "utf8"));
  if (!deployment.contractAddress) throw new Error("contractAddress is missing");
  const output = runGenlayer(
    ["schema", deployment.contractAddress, "--rpc", STUDIONET.rpcUrl],
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
  const receipt = await client.waitForTransactionReceipt({
    hash,
    status: "ACCEPTED",
    interval: 5000,
    retries: 120,
  });
  return receiptSummary(hash, receipt);
}

function safeErrorMessage(error) {
  const message = String(error?.message || error || "");
  if (isTransientStudionetError(error)) {
    return "Studionet RPC rate limited: node is at capacity";
  }
  if (message.includes("insufficient funds")) {
    return "account has insufficient funds";
  }
  if (message.includes("execution reverted") || message.includes("revert")) {
    return "transaction reverted";
  }
  return message.slice(0, 180) || "unknown error";
}

function writeLifecycle(lifecycle, lifecyclePath = DRIFT_PAYOUT_PATH) {
  ensureEvidenceDir();
  writeFileSync(lifecyclePath, JSON.stringify(lifecycle, null, 2) + "\n");
}

function loadResumableLifecycle(lifecyclePath, contractAddress, sponsorAddress, challengerAddress) {
  if (!existsSync(lifecyclePath)) return null;
  try {
    const lifecycle = JSON.parse(readFileSync(lifecyclePath, "utf8"));
    if (String(lifecycle.contractAddress || "").toLowerCase() !== contractAddress.toLowerCase()) {
      return null;
    }
    if (String(lifecycle.sponsor || "").toLowerCase() !== sponsorAddress.toLowerCase()) {
      return null;
    }
    if (String(lifecycle.challenger || "").toLowerCase() !== challengerAddress.toLowerCase()) {
      return null;
    }
    if (!["IN_PROGRESS", "FAILED_PARTIAL"].includes(String(lifecycle.status || ""))) {
      return null;
    }
    lifecycle.status = "IN_PROGRESS";
    lifecycle.txs = lifecycle.txs || {};
    lifecycle.canonicalReads = lifecycle.canonicalReads || {};
    return lifecycle;
  } catch {
    return null;
  }
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
      if (!isTransientStudionetError(message)) {
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

async function demo(options = {}) {
  const lifecyclePath = options.lifecyclePath || DRIFT_PAYOUT_PATH;
  const targetVersion = options.targetVersion || "2.0.0";
  const recoveryMode = Boolean(options.recoveryMode);
  const config = requireStudionetConfig();
  if (!existsSync(DEPLOYMENT_PATH)) throw new Error("deployment.json is missing");
  const deployment = JSON.parse(readFileSync(DEPLOYMENT_PATH, "utf8"));
  if (!deployment.contractAddress) throw new Error("contractAddress is missing");
  const { createAccount, createClient } = await import("genlayer-js");
  const { studionet } = await import("genlayer-js/chains");
  const sponsor = createAccount(readPrivateKey(config.env, PRIVATE_KEY_NAMES));
  const challenger = createAccount(readPrivateKey(config.env, CHALLENGER_KEY_NAMES));
  const sponsorClient = createClient({
    chain: studionet,
    endpoint: STUDIONET.rpcUrl,
    account: sponsor,
  });
  const challengerClient = createClient({
    chain: studionet,
    endpoint: STUDIONET.rpcUrl,
    account: challenger,
  });
  const reader = createClient({ chain: studionet, endpoint: STUDIONET.rpcUrl });
  const chainId = await reader.request({ method: "eth_chainId", params: [] });
  if (chainId !== STUDIONET.chainId) throw new Error("studionet chain id mismatch");

  const existingLifecycle = loadResumableLifecycle(
    lifecyclePath,
    deployment.contractAddress,
    sponsor.address,
    challenger.address,
  );
  const suffix = existingLifecycle?.covenantId
    ? String(existingLifecycle.covenantId).replace(/^dld-/, "")
    : Date.now().toString(36);
  const covenantId = existingLifecycle?.covenantId || `dld-${suffix}`;
  const caseId = existingLifecycle?.caseId || `case-${suffix}`;
  const lifecycle =
    existingLifecycle || {
      network: STUDIONET.network,
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
  writeLifecycle(lifecycle, lifecyclePath);
  try {
    if (!isAcceptedExplorerStatus(lifecycle.txs.activate?.status)) {
      if (lifecycle.txs.activate?.txHash) {
        lifecycle.txs.activate = await waitAccepted(
          sponsorClient,
          lifecycle.txs.activate.txHash,
        );
      } else {
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
              writeLifecycle(lifecycle, lifecyclePath);
            },
          },
        );
      }
      writeLifecycle(lifecycle, lifecyclePath);
    }
    if (!isAcceptedExplorerStatus(lifecycle.txs.openCase?.status)) {
      if (lifecycle.txs.openCase?.txHash) {
        lifecycle.txs.openCase = await waitAccepted(
          challengerClient,
          lifecycle.txs.openCase.txHash,
        );
      } else {
        lifecycle.txs.openCase = await writeAccepted(
          challengerClient,
          deployment.contractAddress,
          "open_case",
          [covenantId, caseId, targetVersion],
          1n * GEN,
          {
            onSubmitted(hash) {
              lifecycle.txs.openCase = { txHash: hash, status: "SUBMITTED" };
              writeLifecycle(lifecycle, lifecyclePath);
            },
          },
        );
      }
      writeLifecycle(lifecycle, lifecyclePath);
    }
    if (!isAcceptedExplorerStatus(lifecycle.txs.adjudicate?.status)) {
      if (lifecycle.txs.adjudicate?.txHash) {
        lifecycle.txs.adjudicate = await waitAccepted(
          sponsorClient,
          lifecycle.txs.adjudicate.txHash,
        );
      } else {
        lifecycle.txs.adjudicate = await writeAccepted(
          sponsorClient,
          deployment.contractAddress,
          "adjudicate_case",
          [caseId],
          0n,
          {
            onSubmitted(hash) {
              lifecycle.txs.adjudicate = { txHash: hash, status: "SUBMITTED" };
              writeLifecycle(lifecycle, lifecyclePath);
            },
          },
        );
      }
      writeLifecycle(lifecycle, lifecyclePath);
    }
  } catch (error) {
    lifecycle.status = "FAILED_PARTIAL";
    lifecycle.safeError = safeErrorMessage(error);
    writeLifecycle(lifecycle, lifecyclePath);
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
  try {
    if (recoveryMode) {
      if (!isAcceptedExplorerStatus(lifecycle.txs.recoverRetryable?.status)) {
        if (lifecycle.txs.recoverRetryable?.txHash) {
          lifecycle.txs.recoverRetryable = await waitAccepted(
            challengerClient,
            lifecycle.txs.recoverRetryable.txHash,
          );
        } else {
          lifecycle.txs.recoverRetryable = await writeAccepted(
            challengerClient,
            deployment.contractAddress,
            "recover_retryable",
            [covenantId],
            0n,
            {
              onSubmitted(hash) {
                lifecycle.txs.recoverRetryable = { txHash: hash, status: "SUBMITTED" };
                writeLifecycle(lifecycle, lifecyclePath);
              },
            },
          );
        }
        writeLifecycle(lifecycle, lifecyclePath);
      }
      if (!isAcceptedExplorerStatus(lifecycle.txs.withdrawSponsor?.status)) {
        if (lifecycle.txs.withdrawSponsor?.txHash) {
          lifecycle.txs.withdrawSponsor = await waitAccepted(
            sponsorClient,
            lifecycle.txs.withdrawSponsor.txHash,
          );
        } else {
          lifecycle.txs.withdrawSponsor = await writeAccepted(
            sponsorClient,
            deployment.contractAddress,
            "withdraw_credit",
            [],
            0n,
            {
              onSubmitted(hash) {
                lifecycle.txs.withdrawSponsor = { txHash: hash, status: "SUBMITTED" };
                writeLifecycle(lifecycle, lifecyclePath);
              },
            },
          );
        }
        writeLifecycle(lifecycle, lifecyclePath);
      }
      if (!isAcceptedExplorerStatus(lifecycle.txs.withdrawChallenger?.status)) {
        if (lifecycle.txs.withdrawChallenger?.txHash) {
          lifecycle.txs.withdrawChallenger = await waitAccepted(
            challengerClient,
            lifecycle.txs.withdrawChallenger.txHash,
          );
        } else {
          lifecycle.txs.withdrawChallenger = await writeAccepted(
            challengerClient,
            deployment.contractAddress,
            "withdraw_credit",
            [],
            0n,
            {
              onSubmitted(hash) {
                lifecycle.txs.withdrawChallenger = { txHash: hash, status: "SUBMITTED" };
                writeLifecycle(lifecycle, lifecyclePath);
              },
            },
          );
        }
        writeLifecycle(lifecycle, lifecyclePath);
      }
      const statusAfterRecovery = await readView(
        reader,
        deployment.contractAddress,
        "get_package_status",
        [covenantId],
      );
      const caseAfterRecovery = await readView(
        reader,
        deployment.contractAddress,
        "get_case",
        [caseId],
      );
      const sponsorCreditAfterWithdraw = await readView(
        reader,
        deployment.contractAddress,
        "get_credit",
        [sponsor.address],
      );
      const challengerCreditAfterWithdraw = await readView(
        reader,
        deployment.contractAddress,
        "get_credit",
        [challenger.address],
      );
      const accounting = await readView(reader, deployment.contractAddress, "get_accounting", []);
      lifecycle.status = "ACCEPTED_RECOVERY_WITHDRAWN_NOT_FINALIZED";
      delete lifecycle.safeError;
      lifecycle.canonicalReads = {
        verdictAfterRecovery: verdict,
        challengerCreditBeforeRecovery: challengerCredit,
        retryableStateInferredFromAcceptedRecover: true,
        statusAfterRecovery,
        caseAfterRecovery,
        sponsorCreditAfterWithdraw,
        challengerCreditAfterWithdraw,
        accountingAfterWithdraw: accounting,
      };
      writeLifecycle(lifecycle, lifecyclePath);
      console.log(JSON.stringify(lifecycle, null, 2));
      return;
    }
    if (!isAcceptedExplorerStatus(lifecycle.txs.withdraw?.status)) {
      if (lifecycle.txs.withdraw?.txHash) {
        lifecycle.txs.withdraw = await waitAccepted(
          challengerClient,
          lifecycle.txs.withdraw.txHash,
        );
      } else {
        lifecycle.txs.withdraw = await writeAccepted(
          challengerClient,
          deployment.contractAddress,
          "withdraw_credit",
          [],
          0n,
          {
            onSubmitted(hash) {
              lifecycle.txs.withdraw = { txHash: hash, status: "SUBMITTED" };
              writeLifecycle(lifecycle, lifecyclePath);
            },
          },
        );
      }
      writeLifecycle(lifecycle, lifecyclePath);
    }
  } catch (error) {
    lifecycle.status = "FAILED_PARTIAL";
    lifecycle.safeError = safeErrorMessage(error);
    writeLifecycle(lifecycle, lifecyclePath);
    throw error;
  }
  const accounting = await readView(reader, deployment.contractAddress, "get_accounting", []);
  lifecycle.status = "ACCEPTED_NOT_FINALIZED";
  delete lifecycle.safeError;
  lifecycle.canonicalReads = {
    statusAfterAdjudication,
    verdict,
    challengerCreditBeforeWithdraw: challengerCredit,
    accountingAfterWithdraw: accounting,
  };
  writeLifecycle(lifecycle, lifecyclePath);
  console.log(JSON.stringify(lifecycle, null, 2));
}

function verify() {
  if (!existsSync(DEPLOYMENT_PATH)) throw new Error("deployment.json is missing");
  const deployment = JSON.parse(readFileSync(DEPLOYMENT_PATH, "utf8"));
  const identity = sourceIdentity();
  if (deployment.network !== STUDIONET.network) throw new Error("network mismatch");
  if (deployment.sourceSha256 !== identity.sourceSha256) throw new Error("source hash mismatch");
  console.log(JSON.stringify({ ok: true, network: deployment.network, contractAddress: deployment.contractAddress || "" }, null, 2));
}

async function main() {
  const command = process.argv[2] || "inspect";
  if (command === "inspect") return inspect();
  if (command === "deploy") return deploy();
  if (command === "schema") return schema();
  if (command === "demo") return demo();
  if (command === "recover-demo") {
    return demo({
      lifecyclePath: RECOVERY_PATH,
      targetVersion: "0.0.0-dld-missing",
      recoveryMode: true,
    });
  }
  if (command === "verify") return verify();
  throw new Error(`unknown command: ${command}`);
}

if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
