"""HaltProof: cryptographically auditable emergency-shutdown orchestration.

HaltProof coordinates already-trusted cluster primitives (Slurm, Kubernetes,
IPMI/BMC) to drain, isolate, and power-fence a target node group, and produces
an Ed25519-signed attestation record of exactly what was targeted and what
ran. It does not implement any new low-level shutdown mechanism; it is an
orchestration and audit-proof layer on top of tools operators already trust.
"""

__version__ = "0.1.2"
