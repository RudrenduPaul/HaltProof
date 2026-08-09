Output "/tmp/haltproof-demo/docs/demo-halt-verify.gif"
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

Type "haltproof keygen --output ./demo_key --force"
Enter
Sleep 1s

Type "haltproof halt gpu-pod-a --nodes node-1,node-2 --backend kubernetes --operator-id demo-operator --attestation-key ./demo_key --attestation-log ./attestations.jsonl"
Enter
Sleep 2s

Type "haltproof verify 1 --attestation-log ./attestations.jsonl"
Enter
Sleep 3s
