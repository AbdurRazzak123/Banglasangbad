"""Compatibility shim. The production publisher lives in automation/auto_publish.py."""
from automation.auto_publish import main

if __name__ == '__main__':
    main()
