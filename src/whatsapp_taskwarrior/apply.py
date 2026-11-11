"""`python -m whatsapp_taskwarrior.apply` is the same as the wtw-apply command."""

from .cli import apply_main

if __name__ == "__main__":
    raise SystemExit(apply_main())
