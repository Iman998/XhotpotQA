from xhotpotqa.cli import main

raise SystemExit(main(["upload-hf", *__import__("sys").argv[1:]]))
