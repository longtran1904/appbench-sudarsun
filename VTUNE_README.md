# How to run vtune-server
```
cd vtune_projects
vtune-server --allow-remote-access --data-directory=$PWD
```

# How To Compile Kernel Debug Symbol 
On Ubuntu:
```
sudo apt install ubuntu-dbgsym-keyring

sudo tee /etc/apt/sources.list.d/ddebs.list <<EOF
deb http://ddebs.ubuntu.com $(lsb_release -cs)          main restricted universe multiverse
deb http://ddebs.ubuntu.com $(lsb_release -cs)-updates  main restricted universe multiverse
deb http://ddebs.ubuntu.com $(lsb_release -cs)-proposed main restricted universe multiverse
EOF

sudo apt update
sudo apt install linux-image-$(uname -r)-dbgsym
sudo apt install linux-modules-$(uname -r)-dbgsym
```

# Point Vtune to Kernel Debug Symbol
Using vtune command, add this argument:
`-search-dir=/usr/lib/debug/boot`



One Time Token: `one-time-token=b479b347bcbcfd1823d079a507569c85`
