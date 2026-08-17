import assert from "node:assert/strict";
import test from "node:test";

import { parseExecutionResult, sanitizeReceipt } from "../scripts/deploy_bradbury.mjs";

test("parseExecutionResult reads raw Studio leader receipt shape", () => {
  const receipt = {
    consensus_data: {
      leader_receipt: [
        {
          execution_result: "SUCCESS",
          contract_address: "0xabc0000000000000000000000000000000000001",
        },
      ],
    },
    transaction_hash: "0xdeploy",
  };

  assert.equal(parseExecutionResult(receipt), "SUCCESS");
});

test("parseExecutionResult reads normalized SDK shape", () => {
  const receipt = {
    txExecutionResultName: "SUCCESS",
    txHash: "0xwrite",
  };

  assert.equal(parseExecutionResult(receipt), "SUCCESS");
});

test("sanitizeReceipt keeps only public allowlisted fields", () => {
  const safe = sanitizeReceipt(
    {
      txExecutionResultName: "SUCCESS",
      txHash: "0xabc",
      contractAddress: "0xcontract",
      node_config: { private: true },
      stdout: "must not be saved",
      stderr: "must not be saved",
    },
    { network: "testnet-bradbury", explorerBase: "https://explorer-bradbury.genlayer.com" },
  );

  assert.deepEqual(Object.keys(safe).sort(), [
    "contractAddress",
    "executionResult",
    "explorerUrl",
    "network",
    "txHash",
  ]);
  assert.equal(safe.executionResult, "SUCCESS");
  assert.equal(safe.network, "testnet-bradbury");
  assert.match(safe.explorerUrl, /0xabc/);
  assert.equal("node_config" in safe, false);
  assert.equal("stdout" in safe, false);
  assert.equal("stderr" in safe, false);
});
