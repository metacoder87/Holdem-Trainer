"""Hand / action / card abstractions for NLHE.

NLHE has ~10^164 states - solving without abstraction is hopeless.
The abstractions here reduce that to ~10^4-10^6 states for tractable
postflop subgames.
"""
