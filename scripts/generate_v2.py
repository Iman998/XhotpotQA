from xhotpotqa.cli import main

raise SystemExit(main(["generate-v2", *__import__("sys").argv[1:]]))
