# Controlled recovery campaign v1.0

## Proof sequence

1. Generate a seeded synthetic event sequence.
2. In a reference ledger, ingest the pre-outage prefix at its original receipt
   times and the post-outage suffix five minutes later.
3. In a separate process, commit the prefix one event per transaction to a
   file-backed SQLite ledger in WAL mode with synchronous `FULL`.
4. Terminate that process with exit code `91` through `os._exit`, bypassing
   context-manager cleanup and graceful database close.
5. Reopen the ledger locally and retransmit the entire sequence at the later
   receipt time.
6. Confirm the prefix is duplicate, the suffix is accepted, and the final count
   has no loss or duplication.
7. Replay the recovered ledger and require exact digest equality with the
   uninterrupted reference.
8. Build and independently verify the recovered evidence bundle.

The workspace is write-once: the campaign refuses an existing path.

## Expected default result

With `count=8` and `crash_after=4`, four committed events survive restart, four
retransmissions are duplicates, four new events are accepted, and the recovered
ledger contains exactly eight events. The CLI returns nonzero if the evidence
bundle does not verify.

## Claim boundary

This campaign proves application-process termination recovery under the local
SQLite configuration used by the test. It does not emulate power removal,
filesystem corruption, disk-cache loss, broker implementation behavior or a
specific device. Those require separate hardware and integration campaigns.
