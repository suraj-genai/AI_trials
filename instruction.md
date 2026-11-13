/app/store/ holds a storage engine's crash-recovery build. It rebuilds the
committed key-value table from a write-ahead journal after a crash. Run it with:

```bash
python3 /app/store/main.py
```

It reads `/app/data/journal.log`, recovers the table, and writes
`/app/output/state.json` and `/app/output/findings.json`.

It is the wrong build: it recovers clean journals correctly, but it mishandles
several of the cases a real crash produces, so on a journal that carries them it
rebuilds the wrong table.

Repair it, in place, under `/app/store/`.

## The contract

`/app/data/WAL_FORMAT.md` is the authority on the journal layout and on how
recovery must read it — the durable log, commits, checkpoints and the redo
pass, each named as a rule. Where the shipped build and the contract disagree,
the build is what is wrong. The contract says nothing about how a program
should be structured, and you may restructure it however you like as long as the
entry points below keep their names and signatures.

`/app/data/samples/` holds three journals with the table each one recovers to,
in `state.json` beside it. They are clean windows; use them to check your work.
`/app/data/journal.log` is the engine's own crashed journal.

## What is graded

Your build is run over fresh journals that are not in this image — journals that
exercise the full range of crash cases the contract describes — and the table it
recovers is compared, key for key and value for value, against the table the
reference build recovers from the identical bytes. There is no partial credit.

## Outputs

`main(data_dir=None, output_dir=None)` must write, under `output_dir`:

- `state.json` — the recovered table as a JSON object mapping each surviving
  key (string) to its integer value.
- `findings.json` — `{"rules": [...]}`, the recovery rules the shipped build
  got wrong, each named from the vocabulary WAL_FORMAT.md lists. Name exactly
  the rules the shipped build violates: no more, no fewer.

When deciding which rules to report, attribute violations to the shipped
build's own logic. Report a rule only when the shipped build independently
violates that rule's semantics; do not add another rule merely because a
different bug causes incorrect downstream state, inputs, or behavior associated
with that rule.

Keep these entry points where they are, with their present names and signatures:
`parse_line(line)` and `durable_prefix(lines)` in `wal.py`, `recover(lines)` in
`recovery.py`, and `main(data_dir=None, output_dir=None)` in `main.py`.

