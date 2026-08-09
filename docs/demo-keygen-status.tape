Output "/tmp/haltproof-demo/docs/demo-keygen-status.gif"
Set FontSize 16
Set Width 760
Set Height 260
Set Theme "Dracula"
Set WindowBar Colorful
Set WindowBarSize 36

Type "export PS1='$ '"
Enter
Sleep 300ms
Type "export HOME=/tmp/haltproof-demo"
Enter
Sleep 300ms

Type "source .venv/bin/activate"
Enter
Sleep 500ms

Type "haltproof keygen --output ./demo_key"
Enter
Sleep 1s

Type "haltproof status --json"
Enter
Sleep 2s
